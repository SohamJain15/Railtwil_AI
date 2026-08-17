from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

class SystemMode(str, Enum): DEMO="DEMO"; VALIDATION="VALIDATION"
class ValidationStrategy(str, Enum): NO_INTERVENTION="NO_INTERVENTION"; RULE_BASED="RULE_BASED"; RAIL_TWIN="RAIL_TWIN"
class RunStatus(str, Enum): QUEUED="QUEUED"; RUNNING="RUNNING"; COMPLETED="COMPLETED"; FAILED="FAILED"

@dataclass
class StrategyResult:
    scenario_id: str; seed: int; strategy: ValidationStrategy; status: str; metrics: dict[str, Any]
    elapsed_seconds: float; safety_status: str = "NOT_APPLICABLE"; failure: str | None = None
    model_versions: dict[str,str] = field(default_factory=dict); selected_action: dict[str,Any] | None = None

@dataclass
class ValidationRun:
    run_id: UUID = field(default_factory=uuid4); status: RunStatus = RunStatus.QUEUED; created_at: str = ""
    completed_at: str | None = None; progress_completed: int = 0; progress_total: int = 0
    seeds: list[int] = field(default_factory=list); scenario_ids: list[str] = field(default_factory=list)
    dataset_version: str = "vasai-seed-v1"; simulation_version: str = "vasai-prototype-v1"
    runtime_info: dict[str,Any] = field(default_factory=dict); results: list[StrategyResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

@dataclass
class ValidationSummary:
    run_id: str; strategy_runs: int; scenario_count: int; successful: int; failed: int
    unsafe_recommendations: int; no_feasible_solution: int; average_delay_reduction_percent: float
    average_conflict_reduction_percent: float; average_throughput_change_percent: float
    eta_mae: float | None = None; conflict_f1: float | None = None
