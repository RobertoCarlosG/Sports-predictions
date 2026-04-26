import datetime as dt
import os
from pathlib import Path

import joblib
import numpy as np

from app.ml.predictor import MlbPredictionService, _half_run_total_line, ensure_model_exists, resolve_model_path
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
    assert pr.model_version.startswith("rf-synthetic-v0@")


def test_resolve_model_path_default() -> None:
    p = resolve_model_path("")
    assert p.name == "model.joblib"


def test_over_under_line_uses_half_run_bucket() -> None:
    assert _half_run_total_line(8.7) == 8.5
    assert _half_run_total_line(7.2) == 7.5


def test_prediction_service_reloads_when_model_file_changes(tmp_path: Path) -> None:
    mp = tmp_path / "m.joblib"
    joblib.dump({"model_version": "rf-a"}, mp)
    svc = MlbPredictionService(mp)
    v1 = svc.model_version

    joblib.dump({"model_version": "rf-b"}, mp)
    stat = mp.stat()
    os.utime(mp, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

    v2 = svc.model_version
    assert v1 != v2
    assert v2.startswith("rf-b@")
