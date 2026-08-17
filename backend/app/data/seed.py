from pathlib import Path
import pandas as pd
from app.data.validator import validate_seed
from app.data.store import SEED, read_seed
from datetime import datetime, timezone
from sqlalchemy import text
from app.db import engine

def load_and_validate():
    nodes, edges, platforms = read_seed("nodes.csv"), read_seed("tracks.csv"), read_seed("platforms.csv")
    trains, timetable = read_seed("trains.csv"), read_seed("timetables.csv")
    for row in trains: row["scheduled_departure"] = pd.Timestamp(row["scheduled_departure"]); row["scheduled_arrival"] = pd.Timestamp(row["scheduled_arrival"])
    for row in timetable: row["scheduled_departure"] = pd.Timestamp(row["scheduled_departure"]); row["scheduled_arrival"] = pd.Timestamp(row["scheduled_arrival"])
    report = validate_seed(nodes, edges, platforms, trains, timetable)
    if not report.valid: raise ValueError("Seed validation failed: " + "; ".join(report.errors))
    return {"nodes": nodes, "edges": edges, "platforms": platforms, "trains": trains, "timetable": timetable, "blocks": read_seed("blocks.csv"), "junctions": read_seed("junctions.csv"), "routes": read_seed("routes.csv"), "constraints": read_seed("operational_constraints.csv")}

async def seed_database() -> bool:
    """Idempotently load the demo station namespace when PostGIS is available."""
    data = load_and_validate(); now = datetime.now(timezone.utc)
    try:
        async with engine.begin() as conn:
            for row in data["nodes"]:
                if row["node_type"] != "station": continue
                await conn.execute(text("""INSERT INTO stations (id, station_code, name, latitude, longitude, zone, station_type, source_name, source_type, source_timestamp, ingested_at, data_quality, is_synthetic, scenario_id)
                    VALUES (:id, :code, :name, :lat, :lon, 'Western', :type, 'project-approved-vasai-layout', 'infrastructure', :now, :now, 0.85, true, 'vasai-disruption-v1')
                    ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, ingested_at=EXCLUDED.ingested_at"""), {"id":row["node_id"],"code":row["node_id"][:10].upper(),"name":row["name"],"lat":row["latitude"],"lon":row["longitude"],"type":"junction" if row["node_id"]=="vasai_road" else "station","now":now})
        return True
    except Exception:
        return False

if __name__ == "__main__":
    data = load_and_validate(); print(f"Validated demo seed: {len(data['trains'])} trains, {len(data['edges'])} tracks, {len(data['platforms'])} platforms")
