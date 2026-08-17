from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

class TrainStatus(str, Enum):
    SCHEDULED="SCHEDULED"; DEPARTED="DEPARTED"; RUNNING="RUNNING"; WAITING="WAITING"; HELD="HELD"
    ARRIVING="ARRIVING"; DWELLING="DWELLING"; DEPARTED_STATION="DEPARTED_STATION"; DELAYED="DELAYED"
    COMPLETED="COMPLETED"; CANCELLED="CANCELLED"

@dataclass
class DelayBreakdown:
    base_schedule_delay: float = 0; dwell_delay: float = 0; block_wait_delay: float = 0
    junction_wait_delay: float = 0; platform_wait_delay: float = 0; headway_wait_delay: float = 0
    event_delay: float = 0
    @property
    def total_delay(self) -> float: return sum(self.__dict__.values())

@dataclass
class TrainState:
    train_id: str; current_node: str; route_id: str; route_nodes: list[str]
    scheduled_time: float; predicted_time: float; priority: int; next_node: str | None = None
    current_block: str | None = None; current_platform: str | None = None; position_m: float = 0
    speed_kmph: float = 0; status: TrainStatus = TrainStatus.SCHEDULED
    next_station: str | None = None; occupancy_start: float | None = None; occupancy_end: float | None = None
    breakdown: DelayBreakdown = field(default_factory=DelayBreakdown)
    @property
    def delay_seconds(self) -> float: return self.breakdown.total_delay

@dataclass
class OccupancyInterval:
    resource_id: str; train_id: str; start: float; end: float; kind: str

@dataclass
class DelayCause:
    cause_type: str; cause_entity: str; affected_train: str; resource: str
    added_delay_seconds: float; timestamp: float

@dataclass
class DelayEvent:
    event_id: UUID = field(default_factory=uuid4); timestamp: float = 0; target_type: str = "train"
    target_id: str = ""; delay_seconds: float = 0; reason: str = ""; severity: str = "MEDIUM"; scenario_id: str = ""

@dataclass
class Conflict:
    conflict_id: str; type: str; severity: str; resource_id: str; train_ids: list[str]
    predicted_time: float; probability: float; current_delay: float; downstream_impact: float; status: str = "OPEN"

@dataclass
class MetricSnapshot:
    time: float; total_delay_minutes: float; active_conflicts: int; predicted_conflicts: int
    throughput_trains_per_hour: float; platform_utilization: float; track_utilization: float
    junction_utilization: float; average_headway: float; prediction_error: float | None = None

@dataclass
class SimulationSnapshot:
    time: float; trains: dict[str, TrainState]; occupancies: list[OccupancyInterval]
    conflicts: list[Conflict]; metrics: MetricSnapshot

@dataclass
class DigitalTwinState:
    simulation_id: UUID = field(default_factory=uuid4); simulation_time: float = 0
    network_version: str = "vasai-prototype-v1"; trains: dict[str, TrainState] = field(default_factory=dict)
    blocks: dict[str, Any] = field(default_factory=dict); platforms: dict[str, Any] = field(default_factory=dict)
    junctions: dict[str, Any] = field(default_factory=dict); routes: dict[str, Any] = field(default_factory=dict)
    active_events: list[DelayEvent] = field(default_factory=list); active_conflicts: list[Conflict] = field(default_factory=list)
    predictions: list[dict[str, Any]] = field(default_factory=list); recommendations: list[dict[str, Any]] = field(default_factory=list)
    occupancies: list[OccupancyInterval] = field(default_factory=list); snapshots: list[SimulationSnapshot] = field(default_factory=list)
    delay_causes: list[DelayCause] = field(default_factory=list)
    def clone(self) -> "DigitalTwinState": return deepcopy(self)
