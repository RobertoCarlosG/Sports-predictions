"""Servicio de inferencia NBA (3 cabezas: moneyline, spread, totals).

Reutiliza los helpers de firma/alineación de `ml/predictor.py` y la calibración
sport-neutral de `ml/calibration.py`. Un bundle NBA es:
    {clf, reg_margin, reg_total, feature_names, model_version}
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from numpy.typing import NDArray

from app.ml.calibration import apply_calibration, load_calibration
from app.ml.nba_features import build_nba_feature_matrix_row
from app.ml.predictor import (
    _model_signature,
    _model_version_with_signature,
    _ModelSignature,
)
from app.models.nba import NbaGameFeatureSnapshot

log = logging.getLogger(__name__)

# Desviación estándar típica del total de puntos NBA (para derivar P(over) del
# regresor de totales). Aproximación honesta sin almacenar residuales por modelo.
_TOTAL_POINTS_STD = 13.0


def _half_line(value: float) -> float:
    """Línea estilo casa de apuestas: siempre .5 derivada de la estimación."""
    return math.floor(value) + 0.5


def _over_probability(total_estimate: float, line: float) -> float:
    """P(total > line) bajo una normal centrada en la estimación del modelo."""
    z = (line - total_estimate) / _TOTAL_POINTS_STD
    over = 0.5 * math.erfc(z / math.sqrt(2.0))
    return max(0.0, min(1.0, over))


@dataclass
class NbaPredictionResult:
    game_id: str
    home_win_probability: float
    margin_estimate: float
    total_points_estimate: float
    spread_line: float
    over_under_line: float
    over_probability: float
    model_version: str
    defaults_injected: bool = False


class NbaPredictionService:
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._bundle: dict[str, Any] | None = None
        self._signature: _ModelSignature | None = None

    def _load(self) -> dict[str, Any]:
        if not self._model_path.is_file():
            raise FileNotFoundError(f"Model not found: {self._model_path}")
        signature = _model_signature(self._model_path)
        if self._bundle is None or self._signature != signature:
            bundle = dict(joblib.load(self._model_path))
            base_version = str(bundle.get("model_version") or "nba-v0")
            bundle["model_base_version"] = base_version
            bundle["model_version"] = _model_version_with_signature(base_version, signature)
            self._bundle = bundle
            self._signature = signature
        return self._bundle

    @property
    def model_version(self) -> str:
        return str(self._load().get("model_version") or "nba-v0")

    def reload(self) -> dict[str, Any]:
        self._bundle = None
        self._signature = None
        return self._load()

    def predict(
        self,
        game_id: str,
        snapshot: NbaGameFeatureSnapshot | None = None,
    ) -> NbaPredictionResult:
        bundle = self._load()
        clf: Any = bundle["clf"]
        reg_margin: Any = bundle["reg_margin"]
        reg_total: Any = bundle["reg_total"]
        # El vector NBA siempre tiene len(NBA_FEATURE_NAMES) columnas y los modelos se
        # entrenan con el mismo conjunto, así que no hace falta alinear (además CatBoost
        # reporta n_features_in_=0 tras joblib.load, lo que rompería un recorte por shape).
        x: NDArray[np.float64] = build_nba_feature_matrix_row(snapshot)
        defaults_injected = bool(x[0, -1])

        proba = clf.predict_proba(x)
        p_home_raw = float(proba[0][1]) if proba.shape[1] > 1 else float(proba[0][0])
        base_version = str(bundle.get("model_base_version") or bundle.get("model_version") or "nba-v0")
        calibrator = load_calibration(base_version)
        p_home = apply_calibration(p_home_raw, calibrator)

        margin = float(reg_margin.predict(x)[0])
        total = float(reg_total.predict(x)[0])
        over_under = _half_line(total)
        # Línea de hándicap del local: negativa si es favorito.
        spread_line = -(round(margin * 2.0) / 2.0)
        return NbaPredictionResult(
            game_id=game_id,
            home_win_probability=p_home,
            margin_estimate=margin,
            total_points_estimate=total,
            spread_line=spread_line,
            over_under_line=over_under,
            over_probability=_over_probability(total, over_under),
            model_version=str(bundle.get("model_version") or "nba-v0"),
            defaults_injected=defaults_injected,
        )


class EnsembleNbaPredictionService:
    """Promedia las salidas de varias variantes (xgb/lgbm/catboost)."""

    def __init__(self, services: list[NbaPredictionService]) -> None:
        if not services:
            raise ValueError("Ensemble requires at least one service")
        self._services = services

    @property
    def model_version(self) -> str:
        return "nba-ensemble@" + "+".join(
            s.model_version.split("@")[0].replace("nba-", "").replace("-db-v1", "") for s in self._services
        )

    def predict(
        self,
        game_id: str,
        snapshot: NbaGameFeatureSnapshot | None = None,
    ) -> NbaPredictionResult:
        results = [s.predict(game_id, snapshot) for s in self._services]
        n = len(results)
        p_home = sum(r.home_win_probability for r in results) / n
        margin = sum(r.margin_estimate for r in results) / n
        total = sum(r.total_points_estimate for r in results) / n
        over_under = _half_line(total)
        return NbaPredictionResult(
            game_id=game_id,
            home_win_probability=p_home,
            margin_estimate=margin,
            total_points_estimate=total,
            spread_line=-(round(margin * 2.0) / 2.0),
            over_under_line=over_under,
            over_probability=_over_probability(total, over_under),
            model_version=self.model_version,
            defaults_injected=any(r.defaults_injected for r in results),
        )
