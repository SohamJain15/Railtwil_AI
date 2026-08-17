from dataclasses import dataclass
from app.simulation.state import DigitalTwinState

@dataclass
class SafetyResult:
    status: str; violations: list[str]

class SafetyValidator:
    def validate(self, state: DigitalTwinState) -> SafetyResult:
        violations: list[str] = []
        for conflict in state.active_conflicts:
            if conflict.type in {"BLOCK_CONFLICT","JUNCTION_CONFLICT","PLATFORM_CONFLICT"}: violations.append(f"{conflict.type}:{conflict.resource_id}")
        for train in state.trains.values():
            if train.speed_kmph > 120: violations.append(f"speed restriction:{train.train_id}")
        return SafetyResult("UNSAFE" if violations else "SAFE", violations)
