import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import networkx as nx
import simpy
from app.data.seed import load_and_validate
from app.simulation.state import *

ROOT = Path(__file__).resolve().parents[3]

class RailwaySimulation:
    """Deterministic SimPy engine. Wall-clock scheduling belongs to SimulationService."""
    def __init__(self, seed: int = 2026, horizon_seconds: float = 7200, snapshot_interval: float = 60, scenario_events: list[dict] | None = None):
        self.seed, self.horizon_seconds, self.snapshot_interval, self.input_scenario_events = seed, horizon_seconds, snapshot_interval, scenario_events
        self.env = simpy.Environment(); self.data = load_and_validate(); self.state = self._initial_state()
        self.resources: dict[str, simpy.Resource] = {}; self.platform_resources: dict[str, simpy.Resource] = {}
        self.junction_resources: dict[str, simpy.Resource] = {}; self.edge_by_pair: dict[tuple[str,str], dict] = {}
        self.graph = nx.Graph(); self.callbacks: list[Callable[[SimulationSnapshot], None]] = []
        self._build_resources(); self._schedule_processes()

    def _initial_state(self) -> DigitalTwinState:
        nodes = {n["node_id"]: n for n in self.data["nodes"]}; edges = self.data["edges"]
        state = DigitalTwinState()
        for p in self.data["platforms"]: state.platforms[p["platform_id"]] = {**p, "occupied_by": None, "occupancy_seconds": 0}
        for b in self.data["blocks"]: state.blocks[b["block_id"]] = {**b, "occupied_by": None}
        # Every traversable edge is a lockable track resource.  Some seeded
        # engineering blocks group an edge under a different identifier, while
        # the remaining prototype edges use their edge identifier directly.
        # Keeping all of them in state makes utilization denominators complete.
        for edge in edges:
            seeded = next((block for block in self.data["blocks"] if block["track_id"] == edge["edge_id"]), None)
            block_id = seeded["block_id"] if seeded else edge["edge_id"]
            state.blocks.setdefault(block_id, {
                "block_id": block_id,
                "track_id": edge["edge_id"],
                "capacity": int(edge["capacity"]),
                "occupied_by": None,
                "provenance": edge.get("provenance", "synthetic prototype topology"),
            })
            state.blocks[block_id].setdefault("capacity", int(edge["capacity"]))
        for j in self.data["junctions"]: state.junctions[j["junction_id"]] = {**j, "occupied_by": None}
        route_by_type = {"FREIGHT":"freight_bypass", "MEMUPASSENGER":"vasai_diva", "EXPRESS":"western_fast"}
        for t in self.data["trains"]:
            origin, destination = t["origin"], t["destination"]
            route_id = route_by_type.get(t["train_type"], "western_slow")
            path = self._path(origin, destination, edges)
            simulation_start = datetime(2026,8,17,8,0,tzinfo=timezone.utc)
            departure = (t["scheduled_departure"].to_pydatetime() - simulation_start).total_seconds()
            arrival = (t["scheduled_arrival"].to_pydatetime() - simulation_start).total_seconds()
            state.trains[t["train_id"]] = TrainState(t["train_id"], origin, route_id, path, departure, arrival, int(t["priority_class"]), next_node=path[1] if len(path)>1 else None, speed_kmph=float(t["max_speed_kmph"]))
        return state

    def _path(self, origin, destination, edges):
        graph = nx.Graph()
        for e in edges: graph.add_edge(e["from_node"], e["to_node"], **e)
        try: return nx.shortest_path(graph, origin, destination, weight="length_m")
        except nx.NetworkXNoPath: return [origin, destination]

    def _build_resources(self):
        for e in self.data["edges"]:
            self.graph.add_edge(e["from_node"], e["to_node"], **e); key = (e["from_node"],e["to_node"]); self.edge_by_pair[key] = e; self.edge_by_pair[(e["to_node"],e["from_node"])] = e
            self.resources[e["edge_id"]] = simpy.Resource(self.env, capacity=max(1, int(e["capacity"])))
        for p in self.data["platforms"]: self.platform_resources[p["platform_id"]] = simpy.Resource(self.env, capacity=1)
        for j in self.data["junctions"]: self.junction_resources[j["junction_id"]] = simpy.Resource(self.env, capacity=1)

    def _schedule_processes(self):
        for train in self.state.trains.values(): self.env.process(self.train_process(train))
        self.env.process(self.event_process())
        self.env.process(self.snapshot_process())

    def _edge(self, a, b): return self.edge_by_pair.get((a,b))
    def _block_id(self, edge):
        for b in self.data["blocks"]:
            if b["track_id"] == edge["edge_id"]: return b["block_id"]
        return edge["edge_id"]

    def _platform_for(self, train):
        rows = [r for r in self.data["timetable"] if r["train_id"] == train.train_id]
        if not rows: return None
        platform = rows[0].get("scheduled_platform")
        return platform or None

    def train_process(self, train: TrainState):
        if train.scheduled_time > 0: yield self.env.timeout(train.scheduled_time)
        train.status = TrainStatus.DEPARTED
        for a, b in zip(train.route_nodes, train.route_nodes[1:]):
            edge = self._edge(a,b)
            if not edge: train.status = TrainStatus.CANCELLED; return
            edge_id = edge["edge_id"]; block_id = self._block_id(edge); resource = self.resources[edge_id]
            request_time = self.env.now
            train.status = TrainStatus.WAITING
            junction_resource = self.junction_resources.get("j_vasai_station") if "vasai_road" in (a,b) else None
            with resource.request() as request:
                yield request
                junction_request = junction_resource.request() if junction_resource else None
                if junction_request:
                    junction_wait_start = self.env.now; yield junction_request; junction_occupancy_start = self.env.now
                    if self.env.now > junction_wait_start: train.breakdown.junction_wait_delay += self.env.now - junction_wait_start
                wait = self.env.now - request_time
                if wait > 0: train.breakdown.block_wait_delay += wait
                train.status = TrainStatus.RUNNING; train.current_block = block_id; train.current_node = a; train.next_node = b; train.occupancy_start = self.env.now
                speed = max(20.0, train.speed_kmph); travel = float(edge["length_m"]) / (speed * 1000 / 3600)
                train.position_m = 0; yield self.env.timeout(travel); train.position_m = float(edge["length_m"]); train.occupancy_end = self.env.now
                self.state.occupancies.append(OccupancyInterval(block_id, train.train_id, train.occupancy_start, train.occupancy_end, "block"))
                if junction_request:
                    self.state.occupancies.append(OccupancyInterval("j_vasai_station", train.train_id, junction_occupancy_start, self.env.now, "junction")); junction_resource.release(junction_request)
            train.current_node = b; train.current_block = None; train.position_m = 0; train.status = TrainStatus.ARRIVING
            platform = self._platform_for(train) if b == "vasai_road" else None
            if platform and platform in self.platform_resources:
                platform_request = self.env.now
                with self.platform_resources[platform].request() as request:
                    yield request; wait = self.env.now-platform_request
                    if wait > 0: train.breakdown.platform_wait_delay += wait
                    train.current_platform = platform; train.status = TrainStatus.DWELLING
                    start = self.env.now; yield self.env.timeout(60); self.state.occupancies.append(OccupancyInterval(platform, train.train_id, start, self.env.now, "platform")); train.current_platform = None
            train.status = TrainStatus.DEPARTED_STATION
            self._tick_train(train)
        train.status = TrainStatus.COMPLETED; self._tick_train(train)

    def event_process(self):
        events = self._scenario_events()
        for event in events:
            if event.timestamp > self.env.now: yield self.env.timeout(event.timestamp-self.env.now)
            self.apply_delay_event(event)

    def _scenario_events(self):
        if self.input_scenario_events is not None:
            return [DelayEvent(timestamp=e["timestamp"], target_type=e.get("target_type","train"), target_id=e.get("target_id",""), delay_seconds=e.get("delay_seconds",0), reason=e.get("reason",e.get("event_type","scenario event")), severity=e.get("severity","MEDIUM"), scenario_id=e.get("scenario_id","validation")) for e in self.input_scenario_events if e.get("event_type","TRAIN_DELAY") in {"TRAIN_DELAY","COMBINED_DELAY"}]
        path = ROOT / "data" / "scenarios" / "scenario_vasai_freight_bottleneck.json"
        raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"events":[]}
        return [DelayEvent(timestamp=e["timestamp"], target_type=e["target_type"], target_id=e["target_id"], delay_seconds=e["delay_seconds"], reason=e["reason"], severity=e["severity"], scenario_id=raw.get("scenario_id","")) for e in raw.get("events",[])]

    def apply_delay_event(self, event: DelayEvent):
        self.state.active_events.append(event); train = self.state.trains.get(event.target_id)
        if not train: return
        train.breakdown.event_delay += event.delay_seconds; train.status = TrainStatus.DELAYED
        self.state.delay_causes.append(DelayCause("EVENT", event.event_id.hex, train.train_id, event.target_id, event.delay_seconds, self.env.now))
        self._propagate_delay(train, event.delay_seconds)

    def _propagate_delay(self, source: TrainState, added: float):
        """Resource-overlap propagation; it never writes downstream delay directly from scenario data."""
        queue = [(source.train_id, added)]; seen = set()
        while queue:
            cause_id, amount = queue.pop(0)
            if cause_id in seen: continue
            seen.add(cause_id)
            source_intervals = [o for o in self.state.occupancies if o.train_id == cause_id]
            source_train = self.state.trains.get(cause_id)
            planned_resources = set()
            if source_train:
                planned_resources = {self._block_id(self._edge(a,b)) for a,b in zip(source_train.route_nodes, source_train.route_nodes[1:]) if self._edge(a,b)}
            for other in self.state.trains.values():
                if other.train_id == cause_id: continue
                overlap = [o for o in self.state.occupancies if o.train_id == other.train_id and any(s.resource_id == o.resource_id and s.start <= o.end + amount and o.start <= s.end + amount for s in source_intervals)]
                other_planned = {self._block_id(self._edge(a,b)) for a,b in zip(other.route_nodes, other.route_nodes[1:]) if self._edge(a,b)}
                planned_overlap = planned_resources & other_planned and abs(other.scheduled_time - (source_train.scheduled_time if source_train else self.env.now)) < 900
                if overlap or planned_overlap:
                    extra = min(180.0, max(30.0, amount * 0.5)); other.breakdown.event_delay += extra
                    resource = overlap[0].resource_id if overlap else next(iter(planned_resources & other_planned), "planned-route"); self.state.delay_causes.append(DelayCause("RESOURCE_OVERLAP", cause_id, other.train_id, resource, extra, self.env.now)); queue.append((other.train_id, extra))

    def snapshot_process(self):
        while self.env.now <= self.horizon_seconds:
            self._capture_snapshot(); yield self.env.timeout(self.snapshot_interval)

    def _tick_train(self, train):
        train.predicted_time = train.scheduled_time + train.delay_seconds; self.state.simulation_time = self.env.now

    def _capture_snapshot(self):
        self.state.simulation_time = self.env.now
        from app.conflicts import ConflictDetector
        ConflictDetector().detect(self.state)
        completed = sum(t.status == TrainStatus.COMPLETED for t in self.state.trains.values())
        total_delay = sum(t.delay_seconds for t in self.state.trains.values()) / 60
        from app.simulation.metrics import calculate_metrics
        measured = calculate_metrics(self.state, max(self.env.now, 1)); metrics = MetricSnapshot(self.env.now, measured["total_delay_minutes"], measured["number_of_conflicts"], 0, measured["throughput_trains_per_hour"], measured["platform_utilization"], measured["track_utilization"], measured["junction_utilization"], measured["average_headway_seconds"], measured["prediction_error_seconds"])
        snapshot = SimulationSnapshot(self.env.now, deepcopy(self.state.trains), list(self.state.occupancies), list(self.state.active_conflicts), metrics); self.state.snapshots.append(snapshot)
        for callback in self.callbacks: callback(snapshot)

    def run(self, until: float | None = None):
        target = min(until or self.horizon_seconds, self.horizon_seconds); self.env.run(until=target); self._capture_snapshot(); return self.state
