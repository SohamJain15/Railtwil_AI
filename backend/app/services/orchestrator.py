from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
from app.conflicts import ConflictDetector
from app.optimization import Action, OptimizationEngine
from app.prediction.service import PredictionService
from app.services.simulation import SimulationService
from app.simulation.state import DelayEvent

class SimulationOrchestrator:
    """Application workflow coordinator; HTTP and WebSocket layers only delegate here."""
    def __init__(self, simulation: SimulationService, predictor: PredictionService, optimizer: OptimizationEngine):
        self.simulation, self.predictor, self.optimizer = simulation, predictor, optimizer
        self.detector = ConflictDetector(); self.events: list[dict[str, Any]] = []; self.before_metrics: dict[str, Any] | None = None

    def _emit(self, event_type: str, payload: dict[str, Any]):
        event = {"type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(), "simulation_id": str(self.simulation.simulation_id) if self.simulation.simulation_id else None, "payload": payload}; self.events.append(event); self.events = self.events[-200:]; return event
    def start_simulation(self, simulation_id: UUID | None = None):
        result = self.simulation.start(simulation_id); self._emit("simulation.started", {"state": self.simulation.state}); return result
    def pause_simulation(self): self.simulation.pause(); return self._emit("simulation.paused", {"state": self.simulation.state})
    def resume_simulation(self): self.simulation.resume(); return self._emit("simulation.resumed", {"state": self.simulation.state})
    def reset_simulation(self): self.simulation.reset(); return self._emit("simulation.reset", {"state": self.simulation.state})
    def load_demo(self):
        simulation_id=self.simulation.load_demo(); self._emit("scenario.started",{"scenario_id":"vasai-freight-bottleneck-v1","state":"ready"}); return simulation_id
    def inject_event(self, event: DelayEvent):
        self.simulation.add_event(event); emitted = self._emit("train.delayed", {"train_id":event.target_id,"delay_seconds":event.delay_seconds,"reason":event.reason})
        self.process_predictions(); self.detect_conflicts(); self.generate_recommendations(); return emitted
    def advance_tick(self):
        if self.simulation.engine: self.simulation.engine.run(min(self.simulation.engine.env.now + 60, self.simulation.engine.horizon_seconds)); self.simulation.snapshots = self.simulation.engine.state.snapshots[-100:]
        return self.collect_metrics()
    def process_predictions(self):
        twin = self.simulation.twin
        if not twin: return []
        outputs = []
        for train in twin.trains.values():
            features = {"current_delay_seconds":train.delay_seconds,"distance_remaining_m":train.position_m,"current_speed_kmph":train.speed_kmph,"scheduled_remaining_seconds":max(0,train.predicted_time-twin.simulation_time),"priority_class":train.priority,"current_block_occupancy":0,"platform_occupancy":0,"downstream_train_count":0,"headway_seconds":120,"junction_congestion":0,"time_of_day":8}
            outputs.append({"train_id":train.train_id,"eta":self.predictor.predict("eta",features),"delay":self.predictor.predict("delay",features),"conflict":self.predictor.predict("conflict",features)})
        twin.predictions = outputs; self._emit("prediction.updated", {"count":len(outputs)}); return outputs
    def detect_conflicts(self):
        if not self.simulation.twin: return []
        conflicts = self.detector.detect(self.simulation.twin); [self._emit("conflict.detected", asdict(conflict)) for conflict in conflicts]; return conflicts
    def generate_recommendations(self, horizon_seconds: int = 1200):
        twin = self.simulation.twin
        if not twin: return None
        result = self.optimizer.optimize(twin, horizon_seconds)
        if not result: return None
        recommendation = {"recommendation_id":f"rec-{result.action.train_id}-{result.action.action_type}","recommended_action":asdict(result.action),"objective_score":result.objective_score,"expected_metrics":{"total_delay_seconds":result.total_delay_seconds,"conflicts":result.conflicts},"safety_status":result.safety_status,"alternatives":[asdict(item) for item in self.optimizer.last_results],"reason":f"{result.action.action_type} selected from computed objective scores and safety checks."}; twin.recommendations = [recommendation]; self._emit("recommendation.generated", recommendation); return recommendation
    def apply_controller_action(self, recommendation_id: str, decision: str, modified_action: str | None = None):
        twin = self.simulation.twin; recommendation = next((item for item in (twin.recommendations if twin else []) if item.get("recommendation_id") == recommendation_id), None)
        if not recommendation: raise ValueError("recommendation not found")
        if decision == "accept":
            action = recommendation["recommended_action"]; train = twin.trains.get(action["train_id"]); 
            if train and action["action_type"] == "HOLD_TRAIN": train.breakdown.event_delay += action.get("duration_seconds", 0); train.status = "HELD"
        elif decision == "modify":
            action = recommendation["recommended_action"]; result = self.optimizer.what_if.run(twin, Action(modified_action or action["action_type"], action["train_id"], action.get("duration_seconds", 60)), 1200)
            if result.safety_status != "SAFE": raise ValueError("modified action failed safety validation")
        return self._emit(f"controller.{decision}", {"recommendation_id":recommendation_id})
    def collect_metrics(self):
        items = self.simulation.snapshots
        return asdict(items[-1].metrics) if items else {}
