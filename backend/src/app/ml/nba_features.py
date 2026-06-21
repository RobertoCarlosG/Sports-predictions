"""Construcción del vector de features NBA (espeja ml/features.py).

Misma convención que MLB: la **última** columna es `defaults_injected` (0/1), que
vale 1 si el bloque de rachas se rellenó con constantes (sin historial). Los
defaults de descanso/back-to-back NO activan el flag (son simétricos por equipo).
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from app.models.nba import NbaGameFeatureSnapshot

NBA_FEATURE_NAMES: list[str] = [
    "home_win_pct_roll",
    "away_win_pct_roll",
    "home_pts_for_roll",
    "away_pts_for_roll",
    "home_pts_against_roll",
    "away_pts_against_roll",
    "home_net_rating_roll",
    "away_net_rating_roll",
    "home_pace_roll",
    "away_pace_roll",
    "home_efg_roll",
    "away_efg_roll",
    "home_rest_days",
    "away_rest_days",
    "home_is_b2b",
    "away_is_b2b",
    "home_court_advantage",
    # 1 = bloque de rachas rellenado con constantes (sin snapshot/sin historial); 0 = observado.
    "defaults_injected",
]

# Constantes de imputación (medias de liga aproximadas).
_DEF_WIN_PCT = 0.5
_DEF_PTS = 112.0
_DEF_NET_RATING = 0.0
_DEF_PACE = 99.0
_DEF_EFG = 0.53
_DEF_REST = 2.0
_DEF_B2B = 0.0
HOME_COURT_ADVANTAGE = 1.0


def _build_feature_values_17(
    snapshot: NbaGameFeatureSnapshot | None,
) -> tuple[list[float], bool]:
    """17 números + si hubo imputación del bloque de rachas con constantes."""
    injected = False

    if snapshot is None:
        injected = True
        vals = [
            _DEF_WIN_PCT,
            _DEF_WIN_PCT,
            _DEF_PTS,
            _DEF_PTS,
            _DEF_PTS,
            _DEF_PTS,
            _DEF_NET_RATING,
            _DEF_NET_RATING,
            _DEF_PACE,
            _DEF_PACE,
            _DEF_EFG,
            _DEF_EFG,
            _DEF_REST,
            _DEF_REST,
            _DEF_B2B,
            _DEF_B2B,
            HOME_COURT_ADVANTAGE,
        ]
        return vals, injected

    def _roll(value: float | None, default: float) -> float:
        nonlocal injected
        if value is None:
            injected = True
            return default
        return float(value)

    def _sched(value: float | int | None, default: float) -> float:
        # Descanso/B2B: ausencia → default sin activar `injected` (simétrico).
        return float(value) if value is not None else default

    vals = [
        _roll(snapshot.home_win_pct_roll, _DEF_WIN_PCT),
        _roll(snapshot.away_win_pct_roll, _DEF_WIN_PCT),
        _roll(snapshot.home_pts_for_roll, _DEF_PTS),
        _roll(snapshot.away_pts_for_roll, _DEF_PTS),
        _roll(snapshot.home_pts_against_roll, _DEF_PTS),
        _roll(snapshot.away_pts_against_roll, _DEF_PTS),
        _roll(snapshot.home_net_rating_roll, _DEF_NET_RATING),
        _roll(snapshot.away_net_rating_roll, _DEF_NET_RATING),
        _roll(snapshot.home_pace_roll, _DEF_PACE),
        _roll(snapshot.away_pace_roll, _DEF_PACE),
        _roll(snapshot.home_efg_roll, _DEF_EFG),
        _roll(snapshot.away_efg_roll, _DEF_EFG),
        _sched(snapshot.home_rest_days, _DEF_REST),
        _sched(snapshot.away_rest_days, _DEF_REST),
        _sched(snapshot.home_is_b2b, _DEF_B2B),
        _sched(snapshot.away_is_b2b, _DEF_B2B),
        HOME_COURT_ADVANTAGE,
    ]
    return vals, injected


def build_nba_feature_matrix_row(
    snapshot: NbaGameFeatureSnapshot | None = None,
) -> NDArray[np.float64]:
    """Fila 1×(17+1) alineada con ``NBA_FEATURE_NAMES`` (última columna: 0/1)."""
    vals, injected = _build_feature_values_17(snapshot)
    flag = 1.0 if injected else 0.0
    return np.array([vals + [flag]], dtype=np.float64)


def build_nba_feature_values_for_training(
    snapshot: NbaGameFeatureSnapshot,
) -> list[float]:
    """Lista de 18 floats para `train_nba_from_db` (misma lógica que inferencia)."""
    vals, injected = _build_feature_values_17(snapshot)
    return vals + [1.0 if injected else 0.0]
