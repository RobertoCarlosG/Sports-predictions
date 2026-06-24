"""Tests for app.ml.train_from_db — covering _log_feature_health, _split_temporal,
_build_rf, _build_xgb, main() CLI defaults, and _async_main() pipeline."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import joblib
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from xgboost import XGBClassifier, XGBRegressor

from app.ml.train_from_db import (
    _async_main,
    _build_rf,
    _build_xgb,
    _log_feature_health,
    _split_temporal,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**kwargs: Any) -> argparse.Namespace:
    defaults = dict(
        algorithm="rf",
        trees=10,
        max_depth=4,
        min_samples_leaf=2,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        val_from=None,
        season=None,
        output=None,
        model_version="rf-db-v1",
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _make_xy(n: int = 40) -> tuple[Any, Any, Any, list[dt.date]]:
    """Synthetic (X, y_home, y_runs, dates) for _async_main tests."""
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n, 13))
    y_h = (rng.random(n) > 0.5).astype(int)
    y_r = rng.uniform(4.0, 12.0, size=n).astype(np.float64)
    base = dt.date(2024, 1, 1)
    dates = [base + dt.timedelta(days=i) for i in range(n)]
    return np.asarray(x, dtype=np.float64), np.asarray(y_h, dtype=np.int_), y_r, dates


@asynccontextmanager
async def _fake_session_ctx():
    yield MagicMock()


# ---------------------------------------------------------------------------
# _log_feature_health
# ---------------------------------------------------------------------------


def test_log_feature_health_healthy(caplog: pytest.LogCaptureFixture) -> None:
    rng = np.random.default_rng(1)
    x = rng.normal(size=(50, 13))
    with caplog.at_level(logging.WARNING, logger="app.ml.train_from_db"):
        _log_feature_health(x)
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


def test_log_feature_health_warns_low_nz(caplog: pytest.LogCaptureFixture) -> None:
    x = np.zeros((50, 13))
    with caplog.at_level(logging.WARNING, logger="app.ml.train_from_db"):
        _log_feature_health(x)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "Expected a warning for flat features"
    assert any("planas" in r.message for r in warnings)


def test_log_feature_health_warns_low_mean_std(caplog: pytest.LogCaptureFixture) -> None:
    rng = np.random.default_rng(2)
    # std ~0.005 — nz >= 4 but mean_std << 0.02
    x = rng.normal(scale=0.005, size=(50, 13))
    with caplog.at_level(logging.WARNING, logger="app.ml.train_from_db"):
        _log_feature_health(x)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "Expected a warning for low mean std"


def test_log_feature_health_fewer_than_12_cols(caplog: pytest.LogCaptureFixture) -> None:
    rng = np.random.default_rng(3)
    x = rng.normal(size=(50, 8))  # x.shape[1] <= 12 → x12 = x (no slicing)
    with caplog.at_level(logging.INFO, logger="app.ml.train_from_db"):
        _log_feature_health(x)
    info = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any("rows=50" in r.message for r in info)


# ---------------------------------------------------------------------------
# _split_temporal
# ---------------------------------------------------------------------------


def _build_split_data(n: int) -> tuple[Any, Any, Any, list[dt.date]]:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n, 13))
    y_h = np.zeros(n, dtype=np.int_)
    y_r = np.arange(n, dtype=np.float64)
    base = dt.date(2024, 1, 1)
    dates = [base + dt.timedelta(days=i) for i in range(n)]
    return np.asarray(x, dtype=np.float64), y_h, y_r, dates


def test_split_temporal_val_from_mode() -> None:
    x, y_h, y_r, dates = _build_split_data(30)
    val_from = dates[20]
    x_tr, x_va, yh_tr, yh_va, yr_tr, yr_va, label = _split_temporal(x, y_h, y_r, dates, val_from)
    assert label == "val_from"
    assert x_tr.shape[0] == 20
    assert x_va.shape[0] == 10


def test_split_temporal_80pct_mode() -> None:
    x, y_h, y_r, dates = _build_split_data(30)
    x_tr, x_va, yh_tr, yh_va, yr_tr, yr_va, label = _split_temporal(x, y_h, y_r, dates, None)
    assert label == "80pct"
    assert x_tr.shape[0] == 24
    assert x_va.shape[0] == 6


def test_split_temporal_raises_too_few_train() -> None:
    x, y_h, y_r, dates = _build_split_data(12)
    val_from = dates[3]  # nt=3 < 10
    with pytest.raises(RuntimeError, match="train=3"):
        _split_temporal(x, y_h, y_r, dates, val_from)


def test_split_temporal_raises_too_few_val() -> None:
    x, y_h, y_r, dates = _build_split_data(15)
    val_from = dates[12]  # nv=3 < 5
    with pytest.raises(RuntimeError, match="val=3"):
        _split_temporal(x, y_h, y_r, dates, val_from)


def test_split_temporal_data_integrity() -> None:
    n = 20
    x, y_h, y_r, dates = _build_split_data(n)
    y_r = np.arange(n, dtype=np.float64)  # overwrite with 0..19 for easy assertion
    val_from = dates[15]
    _, _, yh_tr, yh_va, yr_tr, yr_va, _ = _split_temporal(x, y_h, y_r, dates, val_from)
    assert yr_tr.tolist() == list(range(15))
    assert yr_va.tolist() == list(range(15, 20))
    assert len(yh_tr) == 15
    assert len(yh_va) == 5


# ---------------------------------------------------------------------------
# _build_rf
# ---------------------------------------------------------------------------


def test_build_rf_hyperparams() -> None:
    args = _make_args(trees=50, max_depth=10, min_samples_leaf=3)
    clf, reg = _build_rf(args)
    assert isinstance(clf, RandomForestClassifier)
    assert isinstance(reg, RandomForestRegressor)
    assert clf.n_estimators == 50
    assert clf.max_depth == 10
    assert clf.min_samples_leaf == 3
    assert clf.random_state == 42
    assert reg.n_estimators == 50
    assert reg.max_depth == 10


# ---------------------------------------------------------------------------
# _build_xgb
# ---------------------------------------------------------------------------


def test_build_xgb_hyperparams() -> None:
    args = _make_args(
        trees=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.75,
        min_child_weight=2,
    )
    clf, reg = _build_xgb(args)
    assert isinstance(clf, XGBClassifier)
    assert isinstance(reg, XGBRegressor)
    params_clf = clf.get_params()
    assert params_clf["n_estimators"] == 100
    assert params_clf["max_depth"] == 6
    assert params_clf["learning_rate"] == pytest.approx(0.1)
    assert params_clf["subsample"] == pytest.approx(0.9)
    assert params_clf["colsample_bytree"] == pytest.approx(0.75)
    assert params_clf["min_child_weight"] == 2
    assert params_clf["eval_metric"] == "logloss"
    assert clf.random_state == 42
    params_reg = reg.get_params()
    assert params_reg["n_estimators"] == 100
    # regressor should not have logloss eval_metric
    assert params_reg.get("eval_metric") != "logloss"


def test_build_xgb_models_can_fit() -> None:
    args = _make_args(trees=4, max_depth=3)
    clf, reg = _build_xgb(args)
    rng = np.random.default_rng(0)
    x = rng.normal(size=(40, 13))
    y_clf = (x[:, 0] > 0).astype(int)
    y_reg = x.sum(axis=1)
    clf.fit(x, y_clf)
    reg.fit(x, y_reg)
    proba = clf.predict_proba(x)
    assert proba.shape == (40, 2)
    preds = reg.predict(x)
    assert preds.shape == (40,)


# ---------------------------------------------------------------------------
# main() — CLI argument parsing
# ---------------------------------------------------------------------------


def test_main_rf_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[argparse.Namespace] = []

    def fake_run(coro: Any) -> None:  # type: ignore[override]
        # extract args from the coroutine's cr_frame locals
        captured.append(coro.cr_frame.f_locals["args"])
        coro.close()

    monkeypatch.setattr("app.ml.train_from_db.asyncio.run", fake_run)
    main([])
    args = captured[0]
    assert args.algorithm == "rf"
    assert args.max_depth == 16
    assert args.output.endswith("model.joblib") and "model_xgb" not in args.output
    assert args.model_version == "rf-db-v1"


def test_main_xgb_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[argparse.Namespace] = []

    def fake_run(coro: Any) -> None:
        captured.append(coro.cr_frame.f_locals["args"])
        coro.close()

    monkeypatch.setattr("app.ml.train_from_db.asyncio.run", fake_run)
    main(["--algorithm", "xgb"])
    args = captured[0]
    assert args.algorithm == "xgb"
    assert args.max_depth == 6
    assert args.output.endswith("model_xgb.joblib")
    assert args.model_version == "xgb-db-v1"


def test_main_explicit_output_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: list[argparse.Namespace] = []

    def fake_run(coro: Any) -> None:
        captured.append(coro.cr_frame.f_locals["args"])
        coro.close()

    monkeypatch.setattr("app.ml.train_from_db.asyncio.run", fake_run)
    custom = str(tmp_path / "custom.joblib")
    main(["--output", custom])
    assert captured[0].output == custom


def test_main_explicit_max_depth_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[argparse.Namespace] = []

    def fake_run(coro: Any) -> None:
        captured.append(coro.cr_frame.f_locals["args"])
        coro.close()

    monkeypatch.setattr("app.ml.train_from_db.asyncio.run", fake_run)
    main(["--max-depth", "8"])
    assert captured[0].max_depth == 8


def test_main_explicit_model_version_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[argparse.Namespace] = []

    def fake_run(coro: Any) -> None:
        captured.append(coro.cr_frame.f_locals["args"])
        coro.close()

    monkeypatch.setattr("app.ml.train_from_db.asyncio.run", fake_run)
    main(["--model-version", "custom-v99"])
    assert captured[0].model_version == "custom-v99"


# ---------------------------------------------------------------------------
# _async_main — full pipeline (DB monkeypatched)
# ---------------------------------------------------------------------------


def _patch_db(monkeypatch: pytest.MonkeyPatch, n: int = 40) -> None:
    """Patches out all real DB access in train_from_db."""
    monkeypatch.setattr(
        "app.ml.train_from_db.async_session_factory",
        lambda: _fake_session_ctx(),
    )
    monkeypatch.setattr(
        "app.ml.train_from_db._load_xy",
        AsyncMock(return_value=_make_xy(n)),
    )


def test_async_main_xgb_writes_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_db(monkeypatch)
    out = tmp_path / "m.joblib"
    args = _make_args(algorithm="xgb", output=str(out), model_version="xgb-db-v1", trees=4, max_depth=3)
    asyncio.run(_async_main(args))
    assert out.exists()
    bundle = joblib.load(out)
    assert isinstance(bundle["clf"], XGBClassifier)
    assert bundle["model_version"] == "xgb-db-v1"
    meta = json.loads(bundle["training_meta"])
    assert meta["algorithm"] == "xgb"


def test_async_main_rf_writes_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_db(monkeypatch)
    out = tmp_path / "m.joblib"
    args = _make_args(algorithm="rf", output=str(out), model_version="rf-db-v1", trees=4, max_depth=4)
    asyncio.run(_async_main(args))
    bundle = joblib.load(out)
    assert isinstance(bundle["clf"], RandomForestClassifier)
    assert bundle["model_version"] == "rf-db-v1"
    meta = json.loads(bundle["training_meta"])
    assert meta["algorithm"] == "rf"


def test_async_main_val_from_split(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_db(monkeypatch, n=40)
    out = tmp_path / "m.joblib"
    # 40 rows: dates 2024-01-01 to 2024-02-09; val_from=2024-01-28 → 27 train, 13 val
    args = _make_args(
        algorithm="rf",
        output=str(out),
        model_version="rf-db-v1",
        trees=4,
        max_depth=4,
        val_from="2024-01-28",
    )
    asyncio.run(_async_main(args))
    bundle = joblib.load(out)
    meta = json.loads(bundle["training_meta"])
    assert meta["split_mode"] == "val_from"


def test_async_main_bad_val_from_falls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 25 rows (80pct cut=20→nv=5 is valid); val_from on last date → nv=1 → bad → fallback
    _patch_db(monkeypatch, n=25)
    out = tmp_path / "m.joblib"
    # dates[24] = 2024-01-25: nt=24, nv=1 → error → fallback to 80pct (nt=20, nv=5 ✓)
    args = _make_args(
        algorithm="rf",
        output=str(out),
        model_version="rf-db-v1",
        trees=4,
        max_depth=4,
        val_from="2024-01-25",
    )
    with caplog.at_level(logging.WARNING, logger="app.ml.train_from_db"):
        asyncio.run(_async_main(args))
    bundle = joblib.load(out)
    meta = json.loads(bundle["training_meta"])
    assert meta["split_mode"] == "80pct_fallback_after_bad_val_from"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("No se pudo usar val_from" in r.message for r in warnings)


def test_async_main_bad_val_from_none_reraises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # 12 rows, val_from=None → 80/20 cut: 9 train < 10 → RuntimeError raised
    _patch_db(monkeypatch, n=12)
    out = tmp_path / "m.joblib"
    args = _make_args(
        algorithm="rf",
        output=str(out),
        model_version="rf-db-v1",
        trees=4,
        max_depth=4,
        val_from=None,
    )
    with pytest.raises(RuntimeError):
        asyncio.run(_async_main(args))


def test_async_main_creates_nested_output_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_db(monkeypatch)
    out = tmp_path / "nested" / "dir" / "m.joblib"
    args = _make_args(algorithm="rf", output=str(out), model_version="rf-db-v1", trees=4, max_depth=4)
    asyncio.run(_async_main(args))
    assert out.exists()


# ---------------------------------------------------------------------------
# _load_xy — directly with SQLite (covers lines 55-95)
# ---------------------------------------------------------------------------


async def _seed_games(session: Any, n: int = 20, season: str = "2024", start_pk: int = 1) -> None:
    """Insert n Game + GameFeatureSnapshot rows into an async SQLAlchemy session."""
    from app.models.mlb import Game, GameFeatureSnapshot, Team

    if start_pk == 1:
        t1 = Team(id=1, name="Home Team", abbreviation="HT", venue_id=None, venue_name=None)
        t2 = Team(id=2, name="Away Team", abbreviation="AT", venue_id=None, venue_name=None)
        session.add_all([t1, t2])
        await session.flush()

    base = dt.date(2024, 1, 1)
    for i in range(n):
        game = Game(
            game_pk=start_pk + i,
            season=season,
            game_date=base + dt.timedelta(days=start_pk + i - 1),
            game_datetime_utc=None,
            status="Final",
            home_team_id=1,
            away_team_id=2,
            venue_id=None,
            venue_name=None,
            lineups_json=None,
            boxscore_json=None,
        )
        session.add(game)
        await session.flush()
        snap = GameFeatureSnapshot(
            game_pk=start_pk + i,
            home_win=i % 2,
            total_runs=8.0 + float(i % 5),
            home_wins_roll=0.55,
            away_wins_roll=0.45,
        )
        session.add(snap)
    await session.flush()


async def test_load_xy_returns_arrays(sqlite_session_factory: Any) -> None:
    from app.ml.train_from_db import _load_xy

    async with sqlite_session_factory() as session:
        await _seed_games(session, n=20)
        x, y_h, y_r, dates = await _load_xy(session, season=None)

    assert x.shape == (20, 13)
    assert len(y_h) == 20
    assert len(y_r) == 20
    assert len(dates) == 20
    assert all(isinstance(d, dt.date) for d in dates)


async def test_load_xy_season_filter(sqlite_session_factory: Any) -> None:
    from app.ml.train_from_db import _load_xy

    async with sqlite_session_factory() as session:
        await _seed_games(session, n=20, season="2024")
        # Add 5 more games with season 2023 (different game_pks)
        await _seed_games(session, n=5, season="2023", start_pk=21)
        x, y_h, y_r, dates = await _load_xy(session, season="2024")

    assert x.shape == (20, 13)


async def test_load_xy_raises_when_fewer_than_20(sqlite_session_factory: Any) -> None:
    from app.ml.train_from_db import _load_xy

    async with sqlite_session_factory() as session:
        await _seed_games(session, n=10)
        with pytest.raises(RuntimeError, match="Need at least 20"):
            await _load_xy(session, season=None)


# ---------------------------------------------------------------------------
# _async_main — Bayesian branch (lines 222-237)
# ---------------------------------------------------------------------------


def test_async_main_bayesian_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_db(monkeypatch, n=40)

    def fake_run_study(**kwargs: Any) -> dict[str, Any]:
        return {"n_estimators": 4, "max_depth": 3}

    def fake_build_models(algorithm: str, best_params: dict[str, Any]) -> tuple[Any, Any]:
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

        clf = RandomForestClassifier(n_estimators=2, random_state=0)
        reg = RandomForestRegressor(n_estimators=2, random_state=0)
        return clf, reg

    monkeypatch.setattr("app.ml.bayesian_search.run_study", fake_run_study)
    monkeypatch.setattr("app.ml.bayesian_search.build_models_from_params", fake_build_models)

    out = tmp_path / "m.joblib"
    args = _make_args(
        algorithm="rf",
        output=str(out),
        model_version="rf-db-v1",
        trees=4,
        max_depth=4,
        bayesian=True,
        bayesian_trials=3,
    )
    asyncio.run(_async_main(args))
    assert out.exists()


# ---------------------------------------------------------------------------
# _async_main — calibration branch (lines 301-309)
# ---------------------------------------------------------------------------


def test_async_main_calibration_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _patch_db(monkeypatch, n=40)

    fake_calibrator = object()

    def fake_fit(raw_probs: Any, yh_va: Any) -> object:
        return fake_calibrator

    def fake_save(model_version: str, calibrator: object) -> Path:
        return Path("/tmp/cal.pkl")

    monkeypatch.setattr("app.ml.calibration.fit_calibration_from_arrays", fake_fit)
    monkeypatch.setattr("app.ml.calibration.save_calibration", fake_save)

    out = tmp_path / "m.joblib"
    args = _make_args(
        algorithm="rf",
        output=str(out),
        model_version="rf-db-v1",
        trees=4,
        max_depth=4,
        calibrate=True,
    )
    asyncio.run(_async_main(args))
    assert out.exists()
