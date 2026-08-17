from itertools import combinations
from app.simulation.state import DigitalTwinState, Conflict, OccupancyInterval

class ConflictDetector:
    def detect(self, state: DigitalTwinState, horizon: float | None = None) -> list[Conflict]:
        conflicts: list[Conflict] = []; intervals = state.occupancies
        for left, right in combinations(intervals, 2):
            if left.train_id == right.train_id or left.resource_id != right.resource_id: continue
            if left.start < right.end and right.start < left.end:
                ctype = "PLATFORM_CONFLICT" if left.kind == "platform" else "BLOCK_CONFLICT"
                conflicts.append(Conflict(f"{ctype}-{left.train_id}-{right.train_id}-{left.resource_id}", ctype, "HIGH", left.resource_id, [left.train_id,right.train_id], max(left.start,right.start), 1.0, max(state.trains[left.train_id].delay_seconds,state.trains[right.train_id].delay_seconds), 0))
        trains = list(state.trains.values())
        for a, b in combinations(trains, 2):
            if a.route_id == b.route_id and abs(a.scheduled_time-b.scheduled_time) < 120:
                conflicts.append(Conflict(f"HEADWAY-{a.train_id}-{b.train_id}", "HEADWAY_CONFLICT", "MEDIUM", a.route_id, [a.train_id,b.train_id], max(a.scheduled_time,b.scheduled_time), .8, max(a.delay_seconds,b.delay_seconds), 0))
        state.active_conflicts = conflicts
        return conflicts
