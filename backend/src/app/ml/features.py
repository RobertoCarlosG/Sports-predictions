from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from app.models.mlb import Game, GameWeather

FEATURE_NAMES: list[str] = [
    "home_wins_roll",
    "away_wins_roll",
    "home_runs_avg_roll",
    "away_runs_avg_roll",
    "temperature_c",
    "humidity_pct",
    "wind_speed_mps",
    "elevation_m",
]


def build_feature_matrix_row(_game: Game, weather: GameWeather | None) -> NDArray[np.float64]:
    """Build a single row of features; uses placeholders for rolling stats when missing."""
    hw = 0.5
    aw = 0.5
    hra = 4.5
    ara = 4.5
    t = float(weather.temperature_c) if weather and weather.temperature_c is not None else 20.0
    h = float(weather.humidity_pct) if weather and weather.humidity_pct is not None else 50.0
    w = float(weather.wind_speed_mps) if weather and weather.wind_speed_mps is not None else 2.0
    e = float(weather.elevation_m) if weather and weather.elevation_m is not None else 100.0
    return np.array([[hw, aw, hra, ara, t, h, w, e]], dtype=np.float64)
