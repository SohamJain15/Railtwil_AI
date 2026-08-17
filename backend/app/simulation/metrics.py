from collections import defaultdict
from statistics import mean
from app.simulation.state import DigitalTwinState, TrainStatus

def calculate_metrics(state: DigitalTwinState, horizon_seconds: float) -> dict[str, float | int | None]:
    horizon = max(float(horizon_seconds), 1.0)
    delays = [train.delay_seconds for train in state.trains.values()]
    completed = sum(train.status == TrainStatus.COMPLETED for train in state.trains.values())
    by_kind: dict[str, float] = defaultdict(float)
    entries: dict[str, list[float]] = defaultdict(list)
    for interval in state.occupancies:
        by_kind[interval.kind] += max(0.0, min(interval.end, horizon) - max(interval.start, 0.0))
        entries[interval.resource_id].append(interval.start)
    platform_capacity = max(sum(int(resource.get("capacity", 1)) for resource in state.platforms.values()), 1)
    block_capacity = max(sum(int(resource.get("capacity", 1)) for resource in state.blocks.values()), 1)
    junction_capacity = max(sum(int(resource.get("capacity", 1)) for resource in state.junctions.values()), 1)
    headways = []
    for starts in entries.values():
        ordered = sorted(starts); headways.extend(b-a for a,b in zip(ordered, ordered[1:]))
    headway_violations = sum(value < 120 for value in headways)
    return {
        "total_delay_minutes": sum(delays) / 60.0,
        "average_delay_minutes": mean(delays) / 60.0 if delays else 0.0,
        "maximum_delay_minutes": max(delays, default=0.0) / 60.0,
        "number_of_conflicts": len(state.active_conflicts),
        "throughput_trains_per_hour": completed / (horizon / 3600.0),
        "platform_utilization": by_kind["platform"] / (horizon * platform_capacity),
        "track_utilization": by_kind["block"] / (horizon * block_capacity),
        "junction_utilization": by_kind["junction"] / (horizon * junction_capacity),
        "average_headway_seconds": mean(headways) if headways else 0.0,
        "headway_violations": headway_violations,
        "prediction_error_seconds": None,
    }
