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
    # 1 = parte del vector rellenada con constantes (NULL o sin snapshot); 0 = todo observado.
    "defaults_injected",
]


def _build_feature_values_12(
    _game: Game,
    weather: GameWeather | None,
    snapshot: GameFeatureSnapshot | None,
) -> tuple[list[float], bool]:
    """12 números + si hubo imputación explícita con constantes del pipeline (no clima real vía API)."""
    injected = False

    if snapshot is not None:
        if snapshot.home_wins_roll is None:
            injected = True
            hw = 0.5
        else:
            hw = float(snapshot.home_wins_roll)
        if snapshot.away_wins_roll is None:
            injected = True
            aw = 0.5
        else:
            aw = float(snapshot.away_wins_roll)
        if snapshot.home_runs_avg_roll is None:
            injected = True
            hra = 4.5
        else:
            hra = float(snapshot.home_runs_avg_roll)
        if snapshot.away_runs_avg_roll is None:
            injected = True
            ara = 4.5
        else:
            ara = float(snapshot.away_runs_avg_roll)

        if snapshot.temperature_c is not None:
            t = float(snapshot.temperature_c)
        elif weather and weather.temperature_c is not None:
            t = float(weather.temperature_c)
        else:
            injected = True
            t = 20.0

        if snapshot.humidity_pct is not None:
            h = float(snapshot.humidity_pct)
        elif weather and weather.humidity_pct is not None:
            h = float(weather.humidity_pct)
        else:
            injected = True
            h = 50.0

        if snapshot.wind_speed_mps is not None:
            w = float(snapshot.wind_speed_mps)
        elif weather and weather.wind_speed_mps is not None:
            w = float(weather.wind_speed_mps)
        else:
            injected = True
            w = 2.0

        if snapshot.elevation_m is not None:
            e = float(snapshot.elevation_m)
        elif weather and weather.elevation_m is not None:
            e = float(weather.elevation_m)
        else:
            injected = True
            e = 100.0

        if snapshot.home_starter_era is None:
            injected = True
            hse = DEFAULT_ERA
        else:
            hse = float(snapshot.home_starter_era)
        if snapshot.away_starter_era is None:
            injected = True
            ase = DEFAULT_ERA
        else:
            ase = float(snapshot.away_starter_era)
        if snapshot.home_bullpen_era is None:
            injected = True
            hbe = DEFAULT_STAFF_ERA
        else:
            hbe = float(snapshot.home_bullpen_era)
        if snapshot.away_bullpen_era is None:
            injected = True
            abe = DEFAULT_STAFF_ERA
        else:
            abe = float(snapshot.away_bullpen_era)
    else:
        # Sin fila de snapshot: todo el bloque de rachas/ERA es const; clima = weather o chuta fija.
        injected = True
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

    return [hw, aw, hra, ara, t, h, w, e, hse, ase, hbe, abe], injected


def build_feature_matrix_row(
    game: Game,
    weather: GameWeather | None,
    snapshot: GameFeatureSnapshot | None = None,
) -> NDArray[np.float64]:
    """Fila 1×(12+1) alineada con ``FEATURE_NAMES`` (última columna: 0/1 defaults inyectados)."""
    vals, injected = _build_feature_values_12(game, weather, snapshot)
    flag = 1.0 if injected else 0.0
    return np.array([vals + [flag]], dtype=np.float64)


def build_feature_values_for_training(
    game: Game,
    weather: GameWeather | None,
    snapshot: GameFeatureSnapshot,
) -> list[float]:
    """Lista de 13 floats para `train_from_db` (misma lógica que inferencia)."""
    vals, injected = _build_feature_values_12(game, weather, snapshot)
    return vals + [1.0 if injected else 0.0]
