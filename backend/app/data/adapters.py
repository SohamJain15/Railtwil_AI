from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import pandas as pd
from app.schemas import DataMetadata, SourceType

class DataSourceAdapter(ABC):
    def __init__(self, source_name: str, source_type: SourceType, scenario_id: str | None = None):
        self.source_name, self.source_type, self.scenario_id = source_name, source_type, scenario_id
    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]: ...
    def validate(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]: return records
    def normalize(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]: return records
    def get_source_metadata(self) -> DataMetadata:
        now = datetime.now(timezone.utc)
        return DataMetadata(source_name=self.source_name, source_type=self.source_type, source_timestamp=now, ingested_at=now, data_quality=1, is_synthetic=self.source_name.startswith("synthetic"), scenario_id=self.scenario_id)

class FileAdapter(DataSourceAdapter):
    def __init__(self, path: str | Path, source_type: SourceType, scenario_id: str | None = None):
        super().__init__(Path(path).name, source_type, scenario_id); self.path = Path(path)
    def fetch(self):
        if self.path.suffix.lower() == ".csv": return pd.read_csv(self.path).where(pd.notna(pd.read_csv(self.path)), None).to_dict("records")
        return json.loads(self.path.read_text(encoding="utf-8"))

class CSVAdapter(FileAdapter): pass
class JSONAdapter(FileAdapter): pass
class RTISAdapter(DataSourceAdapter):
    def fetch(self): return []
class COAAdapter(RTISAdapter): pass
class ARSTMSAdapter(RTISAdapter): pass
class SignallingAdapter(RTISAdapter): pass
class TimetableAdapter(RTISAdapter): pass
class RailRadarAdapter(RTISAdapter): pass

class SyntheticSimulationAdapter(DataSourceAdapter):
    def __init__(self, records: list[dict[str, Any]] | None = None, scenario_id: str = "vasai-disruption-v1"):
        super().__init__("synthetic-simulation", SourceType.simulation_output, scenario_id); self.records = records or []
    def fetch(self): return self.records
