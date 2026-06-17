"""Tests for XGBoost-specific paths in app.ml.predictor."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import joblib
import numpy as np
import pytest
from xgboost import XGBClassifier, XGBRegressor

from app.ml.features import FEATURE_NAMES
from app.ml.predictor import (
    MAX_MODEL_VERSION_LEN,
    MlbPredictionService,
    _align_feature_vector,
    _model_version_with_signature,
    _ModelSignature,
)
from app.models.mlb import Game, GameWeather

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _write_xgb_bundle(
    path: Path,
    *,
    base_version: str = "xgb-db-v1",
    n_features: int = 13,
) -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(40, n_features))
    y_clf = (x[:, 0] > 0).astype(int)
    y_reg = x.sum(axis=1)
    clf = XGBClassifier(n_estimators=4, max_depth=3, random_state=0, eval_metric="logloss")
    reg = XGBRegressor(n_estimators=4, max_depth=3, random_state=0)
    clf.fit(x, y_clf)
    reg.fit(x, y_reg)
    bundle: dict[str, Any] = {
        "clf": clf,
        "reg": reg,
        "model_version": base_version,
        "feature_names": FEATURE_NAMES[:n_features],
    }
    joblib.dump(bundle, path)


def _make_game() -> Game:
    return Game(
        game_pk=777,
        season="2024",
        game_date=dt.date(2024, 6, 15),
        game_datetime_utc=None,
        status="Scheduled",
        home_team_id=1,
        away_team_id=2,
        venue_id=3289,
        venue_name="Test Stadium",
        lineups_json=None,
        boxscore_json=None,
    )


def _make_weather() -> GameWeather:
    return GameWeather(
        game_pk=777,
        temperature_c=22.0,
        humidity_pct=55.0,
        wind_speed_mps=3.0,
        pressure_mbar=1013.0,
        elevation_m=10.0,
        raw_json=None,
        fetched_at=dt.datetime.now(dt.UTC),
    )


# ---------------------------------------------------------------------------
# _align_feature_vector
# ---------------------------------------------------------------------------


def _clf_with_n_features(n: int) -> Any:
    return SimpleNamespace(n_features_in_=n)


def test_align_exact_match() -> None:
    x = np.ones((1, 13), dtype=np.float64)
    clf = _clf_with_n_features(13)
    reg = _clf_with_n_features(13)
    result = _align_feature_vector(x, clf, reg)
    assert result.shape == (1, 13)
    assert np.array_equal(result, x)


def test_align_trim() -> None:
    x = np.ones((1, 15), dtype=np.float64)
    clf = _clf_with_n_features(13)
    reg = _clf_with_n_features(13)
    result = _align_feature_vector(x, clf, reg)
    assert result.shape == (1, 13)


def test_align_pad() -> None:
    x = np.ones((1, 8), dtype=np.float64)
    clf = _clf_with_n_features(13)
    reg = _clf_with_n_features(13)
    result = _align_feature_vector(x, clf, reg)
    assert result.shape == (1, 13)
    assert np.all(result[0, 8:] == 0.0)


def test_align_clf_none_uses_reg() -> None:
    x = np.ones((1, 13), dtype=np.float64)
    clf = SimpleNamespace()  # no n_features_in_
    reg = _clf_with_n_features(10)
    result = _align_feature_vector(x, clf, reg)
    assert result.shape == (1, 10)


def test_align_both_none_uses_x_shape() -> None:
    x = np.ones((1, 13), dtype=np.float64)
    clf = SimpleNamespace()
    reg = SimpleNamespace()
    result = _align_feature_vector(x, clf, reg)
    assert result.shape == (1, 13)


# ---------------------------------------------------------------------------
# _model_version_with_signature
# ---------------------------------------------------------------------------


def _sig(mtime_ns: int = 0xABCDEF) -> _ModelSignature:
    return _ModelSignature(mtime_ns=mtime_ns, size=100)


def test_version_signature_normal() -> None:
    sig = _sig()
    result = _model_version_with_signature("xgb-db-v1", sig)
    assert result.startswith("xgb-db-v1@")
    assert len(result) <= MAX_MODEL_VERSION_LEN
    assert result.endswith(f"{sig.mtime_ns:x}")


def test_version_signature_truncates_long_base() -> None:
    sig = _sig(mtime_ns=0xAB)
    long_base = "x" * 100
    result = _model_version_with_signature(long_base, sig)
    assert len(result) <= MAX_MODEL_VERSION_LEN
    assert result.endswith(f"@{sig.mtime_ns:x}")


def test_version_signature_empty_base_uses_default() -> None:
    sig = _sig()
    result = _model_version_with_signature("", sig)
    assert result.startswith("rf-v0@")


# ---------------------------------------------------------------------------
# MlbPredictionService._load() — XGBoost path
# ---------------------------------------------------------------------------


def test_load_xgb_no_rf_log(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    mp = tmp_path / "m.joblib"
    _write_xgb_bundle(mp)
    svc = MlbPredictionService(mp)
    with caplog.at_level("INFO", logger="app.ml.predictor"):
        _ = svc.model_version
    assert not any("Loaded Random Forest model" in r.message for r in caplog.records)


def test_load_caches_on_same_signature(tmp_path: Path) -> None:
    mp = tmp_path / "m.joblib"
    _write_xgb_bundle(mp)
    svc = MlbPredictionService(mp)
    bundle1 = svc._load()
    bundle2 = svc._load()
    assert bundle1 is bundle2


def test_load_raises_file_not_found(tmp_path: Path) -> None:
    svc = MlbPredictionService(tmp_path / "nonexistent.joblib")
    with pytest.raises(FileNotFoundError, match="Model not found"):
        svc._load()


# ---------------------------------------------------------------------------
# MlbPredictionService.predict() with XGBoost
# ---------------------------------------------------------------------------


def test_predict_xgb_roundtrip(tmp_path: Path) -> None:
    mp = tmp_path / "m.joblib"
    _write_xgb_bundle(mp)
    svc = MlbPredictionService(mp)
    pr = svc.predict(_make_game(), _make_weather())
    assert 0.0 <= pr.home_win_probability <= 1.0
    assert np.isfinite(pr.total_runs_estimate)
    assert pr.model_version.startswith("xgb-db-v1@")
    assert pr.game_pk == 777


def test_predict_xgb_with_feature_trim(tmp_path: Path) -> None:
    # Bundle trained on 8 features; build_feature_matrix_row returns 13 → _align trims
    mp = tmp_path / "m8.joblib"
    _write_xgb_bundle(mp, n_features=8)
    svc = MlbPredictionService(mp)
    pr = svc.predict(_make_game(), _make_weather())
    assert 0.0 <= pr.home_win_probability <= 1.0


# ---------------------------------------------------------------------------
# MlbPredictionService.reload()
# ---------------------------------------------------------------------------


def test_reload_clears_and_reloads(tmp_path: Path) -> None:
    mp = tmp_path / "m.joblib"
    _write_xgb_bundle(mp, base_version="xgb-v1")
    svc = MlbPredictionService(mp)
    # populate cache
    _ = svc.model_version
    assert svc._bundle is not None
    # reload
    bundle = svc.reload()
    assert isinstance(bundle, dict)
    assert "clf" in bundle
    assert svc._bundle is not None
