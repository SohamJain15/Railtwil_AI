from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.schemas import EventType, SimulationEvent

class SimulationService:
    def __init__(self): self.state = "idle"; self.simulation_id: UUID | None = None; self.events: list[SimulationEvent] = []
    def command(self, action: str, simulation_id: UUID | None = None):
        if action == "start": self.simulation_id = simulation_id or uuid4(); self.state = "running"; typ = EventType.simulation_started
        elif action == "pause": self.state = "paused"; typ = EventType.simulation_tick
        elif action == "reset": self.state = "idle"; self.simulation_id = None; typ = EventType.simulation_completed
        else: raise ValueError(f"unknown simulation action: {action}")
        event = SimulationEvent(event_type=typ, timestamp=datetime.now(timezone.utc), simulation_id=self.simulation_id or uuid4(), payload={"state":self.state})
        self.events.append(event); return event
