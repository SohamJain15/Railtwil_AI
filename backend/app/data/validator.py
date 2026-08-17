from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    @property
    def valid(self): return not self.errors

def validate_seed(nodes, edges, platforms, trains, timetable) -> ValidationReport:
    report = ValidationReport(); node_ids = {n["node_id"] for n in nodes}; platform_ids = {p["platform_id"] for p in platforms}
    for e in edges:
        if e["from_node"] not in node_ids or e["to_node"] not in node_ids: report.errors.append(f"broken track reference: {e['edge_id']}")
        if e["length_m"] <= 0 or e["nominal_speed_kmph"] <= 0: report.errors.append(f"invalid track values: {e['edge_id']}")
    ids = [t["train_id"] for t in trains]
    if len(ids) != len(set(ids)): report.errors.append("duplicate train IDs")
    train_ids = set(ids)
    for row in timetable:
        if row["train_id"] not in train_ids: report.errors.append(f"unknown timetable train: {row['train_id']}")
        if row.get("scheduled_platform") and row["scheduled_platform"] not in platform_ids: report.errors.append(f"invalid platform: {row['scheduled_platform']}")
        if row["scheduled_departure"] < row["scheduled_arrival"]: report.errors.append(f"timetable ordering error: {row['timetable_id']}")
    return report
