from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field

class SourceType(str, Enum):
    timetable = "timetable"; infrastructure = "infrastructure"; movement = "movement"
    signalling = "signalling"; synthetic_event = "synthetic_event"; simulation_output = "simulation_output"

class DataMetadata(BaseModel):
    source_name: str
    source_type: SourceType
    source_timestamp: datetime
    ingested_at: datetime
    data_quality: float = Field(ge=0, le=1)
    is_synthetic: bool
    scenario_id: str | None = None

class EventType(str, Enum):
    simulation_started="simulation.started"; simulation_tick="simulation.tick"; train_updated="train.updated"
    train_delayed="train.delayed"; conflict_detected="conflict.detected"; prediction_updated="prediction.updated"
    scenario_started="scenario.started"; optimization_started="optimization.started"; optimization_completed="optimization.completed"
    recommendation_generated="recommendation.generated"; safety_validated="safety.validated"
    controller_accepted="controller.accepted"; controller_modified="controller.modified"; controller_rejected="controller.rejected"
    simulation_completed="simulation.completed"

class SimulationEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    timestamp: datetime
    simulation_id: UUID
    payload: dict[str, Any] = Field(default_factory=dict)

class Train(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    train_id: str; train_number: str; train_type: str; service_class: str
    origin: str; destination: str; priority_class: int = Field(ge=1, le=5)
    length_m: float = Field(gt=0); max_speed_kmph: float = Field(gt=0)
    scheduled_departure: datetime; scheduled_arrival: datetime

class Platform(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    platform_id: str; station_id: str; platform_number: str; length_m: float
    allowed_train_types: list[str]; capacity: int

class NetworkNode(BaseModel):
    node_id: str; node_type: str; name: str; latitude: float | None = None; longitude: float | None = None

class NetworkEdge(BaseModel):
    edge_id: str; from_node: str; to_node: str; length_m: float; nominal_speed_kmph: float
    direction: str; track_type: str; capacity: int

class NetworkResponse(BaseModel):
    nodes: list[NetworkNode]; edges: list[NetworkEdge]; metadata: DataMetadata

class StatusResponse(BaseModel):
    status: str; environment: str; scenario_id: str; persistence: str; event_transport: str

class SimulationCommand(BaseModel):
    simulation_id: UUID | None = None
    scenario_id: str | None = None

class EventCommand(BaseModel):
    event_type: str; payload: dict[str, Any] = Field(default_factory=dict)

class RecommendationDecision(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    modified_action: str | None = None
