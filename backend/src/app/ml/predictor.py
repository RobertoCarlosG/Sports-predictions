from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from app.ml.features import build_feature_matrix_row
from app.models.mlb import Game, GameFeatureSnapshot, GameWeather


def _align_x_to_forest(
    x: NDArray[np.float64],
    clf: RandomForestClassifier,
    reg: RandomForestRegressor,
) -> NDArray[np.float64]:
    """Recorta a ``n_features_in_`` (modelos viejos 8/12; actual 13 con ``defaults_injected``) o rellena con ceros."""
    n_clf = getattr(clf, "n_features_in_", None)
    n_reg = getattr(reg, "n_features_in_", None)
    n = int(n_clf) if n_clf is not None else (int(n_reg) if n_reg is not None else x.shape[1])
    if n == x.shape[1]:
        return x
    if x.shape[1] > n:
        return x[:, :n]
    return np.hstack([x, np.zeros((1, n - x.shape[1]), dtype=np.float64)])


@dataclass
class PredictionResult:
    game_pk: int
    home_win_probability: float
    total_runs_estimate: float
    over_under_line: float
    model_version: str


class MlbPredictionService:
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._bundle: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._bundle is None:
            if not self._model_path.is_file():
                raise FileNotFoundError(f"Model not found: {self._model_path}")
            self._bundle = joblib.load(self._model_path)
        return self._bundle

    def predict(
        self,
        game: Game,
        weather: GameWeather | None,
        snapshot: GameFeatureSnapshot | None = None,
    ) -> PredictionResult:
        bundle = self._load()
        clf: RandomForestClassifier = bundle["clf"]
        reg: RandomForestRegressor = bundle["reg"]
        x: NDArray[np.float64] = build_feature_matrix_row(game, weather, snapshot)
        x = _align_x_to_forest(x, clf, reg)
        proba = clf.predict_proba(x)
        p_home = float(proba[0][1]) if proba.shape[1] > 1 else float(proba[0][0])
        total_runs = float(reg.predict(x)[0])
        model_version = str(bundle.get("model_version") or "rf-v0")
        return PredictionResult(
            game_pk=game.game_pk,
            home_win_probability=p_home,
            total_runs_estimate=total_runs,
            over_under_line=round(total_runs * 2) / 2,
            model_version=model_version,
        )


def ensure_model_exists(model_path: Path) -> None:
    if not model_path.is_file():
        from app.ml.training import train_default_model

        train_default_model(model_path)


def resolve_model_path(env_path: str) -> Path:
    stripped = env_path.strip()
    if stripped:
        path = Path(stripped)
        return path if path.is_absolute() else Path.cwd() / path
    return Path(__file__).resolve().parent / "artifacts" / "model.joblib"
