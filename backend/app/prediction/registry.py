from datetime import datetime, timezone
from pathlib import Path
import json
import joblib

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

class ModelRegistry:
    def register(self, name, model, features, metrics, version="v1"):
        path = ARTIFACTS / f"{name}-{version}.joblib"; joblib.dump(model, path)
        record = {"model_name":name,"version":version,"trained_at":datetime.now(timezone.utc).isoformat(),"dataset_version":"twin-synthetic-v1","features":features,"metrics":metrics,"artifact_path":str(path)}
        (ARTIFACTS / "registry.json").write_text(json.dumps(self.list() + [record], indent=2), encoding="utf-8"); return record
    def list(self):
        path = ARTIFACTS / "registry.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    def load(self, name):
        records = [r for r in self.list() if r["model_name"] == name]
        if not records: return None, None
        record = records[-1]; path=Path(record["artifact_path"])
        if not path.exists(): path=ARTIFACTS / path.name
        return joblib.load(path), record
