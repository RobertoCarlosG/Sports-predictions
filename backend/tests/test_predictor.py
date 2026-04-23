import datetime as dt
from pathlib import Path

import numpy as np

from app.ml.predictor import MlbPredictionService, ensure_model_exists, resolve_model_path
from app.ml.training import train_default_model
from app.models.mlb import Game, GameWeather


def test_train_and_predict_roundtrip(tmp_path: Path) -> None:
    mp = tmp_path / "m.joblib"
    train_default_model(mp)
    ensure_model_exists(mp)
    svc = MlbPredictionService(mp)
    game = Game(
        game_pk=1,
        season="2024",
        game_date=dt.date(2024, 6, 15),
        game_datetime_utc=None,
        status="Scheduled",
        home_team_id=1,
        away_team_id=2,
        venue_id=3289,
        venue_name="Yankee Stadium",
        lineups_json=None,
        boxscore_json=None,
    )
    w = GameWeather(
        game_pk=1,
        temperature_c=22.0,
        humidity_pct=55.0,
        wind_speed_mps=3.0,
        pressure_mbar=1013.0,
        elevation_m=10.0,
        raw_json=None,
        fetched_at=dt.datetime.now(dt.UTC),
    )
    pr = svc.predict(game, w)
    assert 0.0 <= pr.home_win_probability <= 1.0
    assert np.isfinite(pr.total_runs_estimate)
    assert pr.model_version == "rf-synthetic-v0"


def test_resolve_model_path_default() -> None:
    p = resolve_model_path("")
    assert p.name == "model.joblib"
