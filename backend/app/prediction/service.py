from datetime import datetime, timezone
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from xgboost import XGBRegressor, XGBClassifier
from app.prediction.dataset import FEATURES, generate_dataset
from app.prediction.registry import ModelRegistry

class PredictionService:
    def __init__(self): self.registry = ModelRegistry(); self.models = {}
    def train(self, episodes=20, seed=2026):
        data = generate_dataset(episodes, seed); frame = data.frame; x = frame[FEATURES]; groups = frame["episode_id"]
        splitter = GroupShuffleSplit(n_splits=1, test_size=.2, random_state=seed); train_idx, test_idx = next(splitter.split(x, groups=groups)); metrics = {}
        eta = XGBRegressor(n_estimators=40, max_depth=3, learning_rate=.08, random_state=seed, n_jobs=1); eta.fit(x.iloc[train_idx], frame.iloc[train_idx]["eta_target"]); pred = eta.predict(x.iloc[test_idx]); metrics["eta"] = {"mae":float(mean_absolute_error(frame.iloc[test_idx]["eta_target"],pred)),"rmse":float(mean_squared_error(frame.iloc[test_idx]["eta_target"],pred)**.5)}
        delay = XGBRegressor(n_estimators=40, max_depth=3, learning_rate=.08, random_state=seed, n_jobs=1); delay.fit(x.iloc[train_idx], frame.iloc[train_idx]["delay_target"]); pred = delay.predict(x.iloc[test_idx]); metrics["delay"] = {"mae":float(mean_absolute_error(frame.iloc[test_idx]["delay_target"],pred)),"rmse":float(mean_squared_error(frame.iloc[test_idx]["delay_target"],pred)**.5)}
        conflict = XGBClassifier(n_estimators=40, max_depth=3, learning_rate=.08, random_state=seed, n_jobs=1, eval_metric="logloss"); conflict.fit(x.iloc[train_idx], frame.iloc[train_idx]["conflict_target"]); prob = conflict.predict_proba(x.iloc[test_idx])[:,1]; labels = frame.iloc[test_idx]["conflict_target"]; precision, recall, f1, _ = precision_recall_fscore_support(labels, prob>.5, average="binary", zero_division=0); metrics["conflict"]={"precision":float(precision),"recall":float(recall),"f1":float(f1),"roc_auc":float(roc_auc_score(labels,prob)) if len(set(labels))>1 else None}
        self.models = {"eta":eta,"delay":delay,"conflict":conflict}; records = [self.registry.register(name, model, FEATURES, metrics[name]) for name,model in self.models.items()]; return {"metrics":metrics,"records":records,"rows":len(frame)}
    def predict(self, kind, features: dict):
        model = self.models.get(kind); record = None
        if model is None: model, record = self.registry.load(kind)
        if model is None: return {"status":"LOW_CONFIDENCE","prediction":None,"model_version":None,"feature_summary":features}
        values = np.array([[float(features.get(f,0)) for f in FEATURES]])
        prediction = model.predict(values)[0] if kind != "conflict" else model.predict_proba(values)[0,1]
        return {"status":"OK","prediction":float(prediction),"probability":float(prediction) if kind=="conflict" else None,"model_version":record["version"] if record else "v1","feature_summary":features,"timestamp":datetime.now(timezone.utc).isoformat()}
