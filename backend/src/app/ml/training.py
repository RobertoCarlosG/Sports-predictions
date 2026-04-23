from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from app.ml.features import FEATURE_NAMES


def train_default_model(output_path: Path) -> None:
    """Train placeholder models on synthetic data so inference works before historical ingestion."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    n = 400
    x = rng.normal(size=(n, len(FEATURE_NAMES)))
    y_home = (rng.random(n) > 0.48).astype(int)
    y_runs = rng.uniform(4.0, 12.0, size=n)
    clf = RandomForestClassifier(n_estimators=64, random_state=42, max_depth=8)
    reg = RandomForestRegressor(n_estimators=64, random_state=42, max_depth=8)
    clf.fit(x, y_home)
    reg.fit(x, y_runs)
    bundle = {
        "clf": clf,
        "reg": reg,
        "feature_names": FEATURE_NAMES,
        "model_version": "rf-synthetic-v0",
    }
    joblib.dump(bundle, output_path)
