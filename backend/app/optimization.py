from dataclasses import dataclass, asdict
from copy import deepcopy
from app.conflicts import ConflictDetector
from app.safety import SafetyValidator
from app.simulation.state import DigitalTwinState
from ortools.sat.python import cp_model

@dataclass
class Action:
    action_type: str; train_id: str; duration_seconds: int = 0; target: str | None = None
    reason: str = ""; preconditions: list[str] | None = None

@dataclass
class CandidateResult:
    action: Action; objective_score: float; conflicts: int; total_delay_seconds: float; safety_status: str; constraints_checked: list[str]

class WhatIfEngine:
    def __init__(self, runner_factory): self.runner_factory = runner_factory
    def run(self, state: DigitalTwinState, action: Action, horizon: int = 1200) -> CandidateResult:
        clone = deepcopy(state); train = clone.trains.get(action.train_id)
        if not train: return CandidateResult(action, 1e9, 0, 0, "UNSAFE", ["train exists"])
        if action.action_type == "HOLD_TRAIN": train.breakdown.event_delay += action.duration_seconds; train.status = "HELD"
        elif action.action_type == "RELEASE_EARLIER": train.breakdown.event_delay = max(0, train.breakdown.event_delay-action.duration_seconds)
        elif action.action_type == "CHANGE_PRIORITY" and action.target: train.priority = int(action.target)
        detector = ConflictDetector(); conflicts = detector.detect(clone); safety = SafetyValidator().validate(clone)
        delay = sum(t.delay_seconds for t in clone.trains.values()); score = delay + len(conflicts)*10000 + (0 if safety.status == "SAFE" else 1e8)
        return CandidateResult(action, score, len(conflicts), delay, safety.status, ["headway","block","platform","junction","route"])

class OptimizationEngine:
    def __init__(self, what_if: WhatIfEngine): self.what_if = what_if; self.last_results: list[CandidateResult] = []
    def generate_candidates(self, state: DigitalTwinState) -> list[Action]:
        target = next(iter(state.trains.values()), None)
        if not target: return []
        return [Action("HOLD_TRAIN", target.train_id, 60, reason="Create resource separation"), Action("HOLD_TRAIN", target.train_id, 180, reason="Protect junction clearance"), Action("RELEASE_EARLIER", target.train_id, 60, reason="Reduce accumulated delay"), Action("CHANGE_PRIORITY", target.train_id, target= str(max(1,target.priority-1)), reason="Prioritize service")]
    def optimize(self, state: DigitalTwinState, horizon: int = 1200):
        self.last_results = [self.what_if.run(state, action, horizon) for action in self.generate_candidates(state)]
        safe = [r for r in self.last_results if r.safety_status == "SAFE"]
        candidates = safe or self.last_results
        if not candidates: return None
        model = cp_model.CpModel(); choices = [model.NewBoolVar(f"candidate_{i}") for i in range(len(candidates))]; model.AddExactlyOne(choices)
        model.Minimize(sum(choices[i] * int(max(0, min(2_000_000_000, r.objective_score))) for i,r in enumerate(candidates)))
        solver = cp_model.CpSolver(); solver.parameters.num_search_workers = 1; solver.Solve(model)
        selected = next((r for i,r in enumerate(candidates) if solver.Value(choices[i])), candidates[0]); return selected
