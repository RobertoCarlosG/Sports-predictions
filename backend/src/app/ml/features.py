from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from app.models.mlb import Game, GameFeatureSnapshot, GameWeather
from app.services.pitching_stats import DEFAULT_ERA, DEFAULT_STAFF_ERA

FEATURE_NAMES: list[str] = [
    "home_wins_roll",
    "away_wins_roll",
    "home_runs_avg_roll",
    "away_runs_avg_roll",
    "temperature_c",
    "humidity_pct",
    "wind_speed_mps",
    "elevation_m",
    "home_starter_era",
    "away_starter_era",
    "home_bullpen_era",
    "away_bullpen_era",
]


def build_feature_matrix_row(
    _game: Game,
    weather: GameWeather | None,
    snapshot: GameFeatureSnapshot | None = None,
) -> NDArray[np.float64]:
    """Una fila de features alineada con FEATURE_NAMES.

    Si existe ``snapshot`` (p. ej. tras `rebuild_game_feature_snapshots`), se usan rachas y
    clima persistidos; si no, rachas por defecto y clima del objeto weather en vivo.
    """
    if snapshot is not None:
        hw = float(snapshot.home_wins_roll) if snapshot.home_wins_roll is not None else 0.5
        aw = float(snapshot.away_wins_roll) if snapshot.away_wins_roll is not None else 0.5
        hra = float(snapshot.home_runs_avg_roll) if snapshot.home_runs_avg_roll is not None else 4.5
        ara = float(snapshot.away_runs_avg_roll) if snapshot.away_runs_avg_roll is not None else 4.5
        t = (
            float(snapshot.temperature_c)
            if snapshot.temperature_c is not None
            else (
                float(weather.temperature_c)
                if weather and weather.temperature_c is not None
                else 20.0
            )
        )
        h = (
            float(snapshot.humidity_pct)
            if snapshot.humidity_pct is not None
            else (
                float(weather.humidity_pct)
                if weather and weather.humidity_pct is not None
                else 50.0
            )
        )
        w = (
            float(snapshot.wind_speed_mps)
            if snapshot.wind_speed_mps is not None
            else (
                float(weather.wind_speed_mps)
                if weather and weather.wind_speed_mps is not None
                else 2.0
            )
        )
        e = (
            float(snapshot.elevation_m)
            if snapshot.elevation_m is not None
            else (
                float(weather.elevation_m)
                if weather and weather.elevation_m is not None
                else 100.0
            )
        )
        hse = float(snapshot.home_starter_era) if snapshot.home_starter_era is not None else DEFAULT_ERA
        ase = float(snapshot.away_starter_era) if snapshot.away_starter_era is not None else DEFAULT_ERA
        hbe = float(snapshot.home_bullpen_era) if snapshot.home_bullpen_era is not None else DEFAULT_STAFF_ERA
        abe = float(snapshot.away_bullpen_era) if snapshot.away_bullpen_era is not None else DEFAULT_STAFF_ERA
    else:
        hw = 0.5
        aw = 0.5
        hra = 4.5
        ara = 4.5
        t = float(weather.temperature_c) if weather and weather.temperature_c is not None else 20.0
        h = float(weather.humidity_pct) if weather and weather.humidity_pct is not None else 50.0
        w = float(weather.wind_speed_mps) if weather and weather.wind_speed_mps is not None else 2.0
        e = float(weather.elevation_m) if weather and weather.elevation_m is not None else 100.0
        hse = DEFAULT_ERA
        ase = DEFAULT_ERA
        hbe = DEFAULT_STAFF_ERA
        abe = DEFAULT_STAFF_ERA
    return np.array(
        [[hw, aw, hra, ara, t, h, w, e, hse, ase, hbe, abe]], dtype=np.float64
    )
