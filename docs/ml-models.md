# ML models

XGBoost regressors predict ETA and future delay; an XGBoost classifier predicts conflict probability. Training rows come from controlled twin episodes and are split by episode to prevent leakage. Evaluation reports MAE/RMSE or precision/recall/F1 against scheduled/current-delay/rule thresholds. Missing artifacts produce `LOW_CONFIDENCE`; deterministic simulation and safety rules continue.
