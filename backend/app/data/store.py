from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SEED = ROOT / "data" / "seed"

def read_seed(name: str) -> list[dict]:
    path = SEED / name
    if not path.exists(): return []
    frame = pd.read_csv(path)
    return frame.where(pd.notna(frame), None).to_dict("records")

def metadata(source_type="infrastructure", scenario_id="vasai-disruption-v1"):
    now = datetime.now(timezone.utc).isoformat()
    return {"source_name":"project-approved-vasai-layout", "source_type":source_type, "source_timestamp":now, "ingested_at":now, "data_quality":0.85, "is_synthetic":True, "scenario_id":scenario_id}

def network_payload(): return {"nodes": read_seed("nodes.csv"), "edges": read_seed("tracks.csv"), "metadata": metadata()}
