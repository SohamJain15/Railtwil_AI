import asyncio
import csv
import io
import json
import platform
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from app.conflicts import ConflictDetector
from app.config import get_settings
from app.optimization import OptimizationEngine, WhatIfEngine
from app.safety import SafetyValidator
from app.simulation.engine import RailwaySimulation, ROOT
from app.simulation.metrics import calculate_metrics
from app.simulation.state import DelayCause, DelayEvent
from app.validation.models import *
from app.prediction.registry import ModelRegistry

class ValidationRunner:
    def __init__(self):
        self.runs: dict[UUID, ValidationRun] = {}; self.mode = SystemMode.DEMO; self.lock = threading.RLock(); self.listeners = []
        self.suite = json.loads((ROOT / "data" / "scenarios" / "validation_suite.json").read_text(encoding="utf-8"))
    def set_mode(self, mode: SystemMode): self.mode = mode; return mode
    def start(self, seeds: list[int] | None = None, scenario_ids: list[str] | None = None):
        seeds = seeds or list(range(2026,2036)); available = {item["scenario_id"]:item for item in self.suite["scenarios"]}; selected = scenario_ids or list(available)
        unknown = set(selected)-set(available)
        if unknown: raise ValueError(f"Unknown scenarios: {sorted(unknown)}")
        run = ValidationRun(created_at=datetime.now(timezone.utc).isoformat(), seeds=seeds, scenario_ids=selected, progress_total=len(seeds)*len(selected)*3, runtime_info={"python":platform.python_version(),"platform":platform.platform(),"processor":platform.processor() or "unknown","suite_version":self.suite["version"]})
        with self.lock: self.runs[run.run_id] = run
        threading.Thread(target=self._execute, args=(run.run_id,), daemon=True).start(); return run
    def _emit(self, event_type, payload):
        for listener in self.listeners:
            try: listener({"type":event_type,"timestamp":datetime.now(timezone.utc).isoformat(),"payload":payload})
            except Exception: pass
    def _execute(self, run_id: UUID):
        run = self.runs[run_id]; run.status = RunStatus.RUNNING; scenarios = {item["scenario_id"]:item for item in self.suite["scenarios"]}
        for scenario_id in run.scenario_ids:
            for seed in run.seeds:
                for strategy in ValidationStrategy:
                    try: result = self._episode(scenarios[scenario_id], seed, strategy)
                    except Exception as exc: result = StrategyResult(scenario_id,seed,strategy,"FAILED",{},0,failure=f"{type(exc).__name__}: {exc}")
                    with self.lock: run.results.append(result); run.progress_completed += 1
                    self._emit("validation.progress",{"run_id":str(run_id),"completed":run.progress_completed,"total":run.progress_total,"scenario":scenario_id,"seed":seed,"strategy":strategy.value,"status":result.status})
        run.completed_at = datetime.now(timezone.utc).isoformat(); self._persist(run); run.status = RunStatus.COMPLETED; self._emit("validation.completed",{"run_id":str(run_id),"summary":asdict(self.summary(run_id))})
    def _episode(self, scenario: dict, seed: int, strategy: ValidationStrategy):
        started = time.perf_counter(); simulation = RailwaySimulation(seed=seed,horizon_seconds=7200,snapshot_interval=300,scenario_events=[])
        selected_action = None; safety_status = "NOT_APPLICABLE"
        simulation.env.process(self._scenario_process(simulation, scenario, strategy))
        state = simulation.run(); ConflictDetector().detect(state); metrics = calculate_metrics(state, simulation.horizon_seconds)
        if strategy == ValidationStrategy.RAIL_TWIN:
            optimizer = OptimizationEngine(WhatIfEngine(lambda: RailwaySimulation(scenario_events=[]))); result = optimizer.optimize(state,1200)
            if result:
                selected_action = asdict(result.action); safety_status = result.safety_status
            else: safety_status = "NO_FEASIBLE_SOLUTION"
        return StrategyResult(scenario["scenario_id"],seed,strategy,"SUCCESS",metrics,time.perf_counter()-started,safety_status=safety_status,selected_action=selected_action)
    def _scenario_process(self, simulation, scenario, strategy):
        yield simulation.env.timeout(float(scenario.get("timestamp",0))); event_type = scenario["event_type"]
        if event_type in {"TRAIN_DELAY","COMBINED_DELAY"}:
            simulation.apply_delay_event(DelayEvent(timestamp=simulation.env.now,target_id=scenario["target_id"],delay_seconds=float(scenario.get("delay_seconds",0)),reason=scenario["name"],severity=scenario["severity"],scenario_id=scenario["scenario_id"]))
        if event_type == "PLATFORM_UNAVAILABLE":
            resource = simulation.platform_resources.get(scenario["target_id"])
            if resource:
                with resource.request() as request: yield request; yield simulation.env.timeout(scenario["duration_seconds"])
        if event_type in {"JUNCTION_RESTRICTION","COMBINED_DELAY"}:
            resource = simulation.junction_resources.get(scenario.get("junction_id",scenario.get("target_id")))
            if resource:
                with resource.request() as request: yield request; yield simulation.env.timeout(scenario["duration_seconds"])
        if event_type == "SPEED_RESTRICTION":
            train = simulation.state.trains.get(scenario["target_id"])
            if train:
                previous = train.speed_kmph; train.speed_kmph = float(scenario["speed_kmph"]); yield simulation.env.timeout(scenario["duration_seconds"]); train.speed_kmph = previous
        if strategy == ValidationStrategy.RULE_BASED: self._apply_rule(simulation,scenario)
        elif strategy == ValidationStrategy.RAIL_TWIN: self._apply_system_action(simulation,scenario)
    def _apply_rule(self, simulation, scenario):
        target = simulation.state.trains.get(scenario.get("target_id"));
        if not target: return
        candidates = [train for train in simulation.state.trains.values() if train.train_id != target.train_id and set(train.route_nodes)&set(target.route_nodes)]
        if not candidates: return
        held = max(candidates,key=lambda train:(train.priority,train.scheduled_time)); separation = max((int(row.get("minimum_headway",120)) for row in simulation.data["constraints"]),default=120)
        held.breakdown.headway_wait_delay += separation; simulation.state.delay_causes.append(DelayCause("RULE_BASED_SAFE_HOLD",target.train_id,held.train_id,held.next_node or held.current_node,separation,simulation.env.now))
    def _apply_system_action(self, simulation, scenario):
        target = simulation.state.trains.get(scenario.get("target_id"));
        if not target: return
        candidates = [train for train in simulation.state.trains.values() if train.train_id != target.train_id and set(train.route_nodes)&set(target.route_nodes)]
        if not candidates: return
        held = max(candidates,key=lambda train:(train.delay_seconds,train.priority)); hold = max(30,min(120,target.delay_seconds/4)); held.breakdown.headway_wait_delay += hold; simulation.state.delay_causes.append(DelayCause("RAIL_TWIN_SEPARATION",target.train_id,held.train_id,held.next_node or held.current_node,hold,simulation.env.now))
    def get(self, run_id: UUID): return self.runs.get(run_id)
    def summary(self, run_id: UUID):
        run = self.runs[run_id]; successful=[item for item in run.results if item.status=="SUCCESS"]
        pairs={}
        for item in successful: pairs.setdefault((item.scenario_id,item.seed),{})[item.strategy]=item
        delay_changes=[]; conflict_changes=[]; throughput_changes=[]
        for values in pairs.values():
            base, system = values.get(ValidationStrategy.NO_INTERVENTION), values.get(ValidationStrategy.RAIL_TWIN)
            if not base or not system: continue
            delay_changes.append(self._percent(base.metrics["total_delay_minutes"],system.metrics["total_delay_minutes"])); conflict_changes.append(self._percent(base.metrics["number_of_conflicts"],system.metrics["number_of_conflicts"])); throughput_changes.append(self._change(base.metrics["throughput_trains_per_hour"],system.metrics["throughput_trains_per_hour"]))
        registry={item["model_name"]:item for item in ModelRegistry().list()}; eta_mae=registry.get("eta",{}).get("metrics",{}).get("mae"); conflict_f1=registry.get("conflict",{}).get("metrics",{}).get("f1")
        return ValidationSummary(str(run_id),len(run.results),len(run.scenario_ids),len(successful),len(run.results)-len(successful),sum(item.safety_status=="UNSAFE" for item in run.results),sum(item.safety_status=="NO_FEASIBLE_SOLUTION" for item in run.results),mean(delay_changes) if delay_changes else 0,mean(conflict_changes) if conflict_changes else 0,mean(throughput_changes) if throughput_changes else 0,eta_mae,conflict_f1)
    @staticmethod
    def _percent(before,after): return ((before-after)/before*100) if before else 0.0
    @staticmethod
    def _change(before,after): return ((after-before)/before*100) if before else 0.0
    def export(self, run_id: UUID, format: str):
        run=self.runs[run_id]; payload={"run":{key:value for key,value in asdict(run).items() if key!="results"},"summary":asdict(self.summary(run_id)),"results":[asdict(item) for item in run.results],"methodology":{"strategies":[item.value for item in ValidationStrategy],"metric_source":"SimPy movement and resource occupancy history","limitations":"Controlled synthetic simulation; not operational railway validation."}}
        if format=="json": return json.dumps(payload,indent=2,default=str),"application/json"
        if format=="csv":
            output=io.StringIO(); fields=["scenario_id","seed","strategy","status","total_delay_minutes","number_of_conflicts","throughput_trains_per_hour","platform_utilization","junction_utilization","headway_violations","failure"]; writer=csv.DictWriter(output,fieldnames=fields); writer.writeheader()
            for item in run.results: writer.writerow({"scenario_id":item.scenario_id,"seed":item.seed,"strategy":item.strategy.value,"status":item.status,**{key:item.metrics.get(key) for key in fields if key in item.metrics},"failure":item.failure})
            return output.getvalue(),"text/csv"
        summary=self.summary(run_id); lines=["# RAIL-TWIN Validation Report","","## Methodology",f"Seven controlled scenarios compared across {', '.join(item.value for item in ValidationStrategy)}.","",f"Seeds: {', '.join(map(str,run.seeds))}","", "## Summary",f"- Strategy runs: {summary.strategy_runs}",f"- Successful: {summary.successful}",f"- Failed: {summary.failed}",f"- Average delay reduction: {summary.average_delay_reduction_percent:.2f}%",f"- Average conflict reduction: {summary.average_conflict_reduction_percent:.2f}%","","## Limitations","Controlled synthetic simulation evidence only; no claim of operational railway validation."]
        return "\n".join(lines),"text/markdown"
    def _persist(self, run):
        async def write():
            worker_engine=create_async_engine(get_settings().database_url,poolclass=NullPool)
            try:
                async with worker_engine.begin() as connection: await connection.execute(text("INSERT INTO simulation_records (id,record_type,payload,created_at) VALUES (:id,'validation_run',CAST(:payload AS JSONB),now()) ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload,created_at=now()"),{"id":str(run.run_id),"payload":json.dumps(asdict(run),default=str)})
            finally: await worker_engine.dispose()
        try: asyncio.run(write())
        except Exception as exc: run.errors.append(f"database persistence unavailable: {type(exc).__name__}")
