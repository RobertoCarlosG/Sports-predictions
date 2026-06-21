"""Tests del servicio de inferencia NBA (3 cabezas) + ensemble."""

from __future__ import annotations

import argparse

import joblib
import numpy as np
import pytest

from app.ml.nba_predictor import (
    EnsembleNbaPredictionService,
    NbaPredictionService,
)
from app.ml.train_nba_from_db import _build_models
from app.models.nba import NbaGameFeatureSnapshot


def _train_bundle(algorithm: str, path) -> None:
    ns = argparse.Namespace(
        trees=30, max_depth=4, learning_rate=0.1, subsample=0.9, colsample_bytree=0.9
    )
    rng = np.random.default_rng(0)
    x = rng.random((120, 18))
    y_home = (x[:, 6] > x[:, 7]).astype(int)
    y_margin = (x[:, 6] - x[:, 7]) * 12
    y_total = x[:, 2] + x[:, 3] + 200
    clf, reg_margin, reg_total = _build_models(algorithm, ns)
    clf.fit(x, y_home)
    reg_margin.fit(x, y_margin)
    reg_total.fit(x, y_total)
    joblib.dump(
        {
            "clf": clf,
            "reg_margin": reg_margin,
            "reg_total": reg_total,
            "feature_names": [f"f{i}" for i in range(18)],
            "model_version": f"nba-{algorithm}-test",
        },
        path,
    )


@pytest.mark.parametrize("algorithm", ["xgb", "lgbm", "catboost"])
def test_predict_returns_sane_values(tmp_path, algorithm):
    path = tmp_path / f"model_nba_{algorithm}.joblib"
    _train_bundle(algorithm, path)
    svc = NbaPredictionService(path)
    snap = NbaGameFeatureSnapshot(
        game_id="g1",
        home_win_pct_roll=0.7,
        away_win_pct_roll=0.3,
        home_pts_for_roll=118.0,
        away_pts_for_roll=108.0,
        home_pts_against_roll=105.0,
        away_pts_against_roll=112.0,
        home_net_rating_roll=8.0,
        away_net_rating_roll=-4.0,
        home_pace_roll=101.0,
        away_pace_roll=98.0,
        home_efg_roll=0.57,
        away_efg_roll=0.5,
        home_rest_days=2,
        away_rest_days=1,
        home_is_b2b=0,
        away_is_b2b=1,
    )
    res = svc.predict("g1", snap)
    assert 0.0 <= res.home_win_probability <= 1.0
    assert 0.0 <= res.over_probability <= 1.0
    assert res.over_under_line == np.floor(res.total_points_estimate) + 0.5
    assert res.defaults_injected is False
    assert res.model_version.startswith(f"nba-{algorithm}-test")


def test_predict_with_no_snapshot_flags_defaults(tmp_path):
    path = tmp_path / "model_nba_xgb.joblib"
    _train_bundle("xgb", path)
    svc = NbaPredictionService(path)
    res = svc.predict("g2", None)
    assert res.defaults_injected is True


def test_ensemble_averages_members(tmp_path):
    services = []
    for algo in ("xgb", "lgbm"):
        p = tmp_path / f"model_nba_{algo}.joblib"
        _train_bundle(algo, p)
        services.append(NbaPredictionService(p))
    ens = EnsembleNbaPredictionService(services)
    res = ens.predict("g3", None)
    assert 0.0 <= res.home_win_probability <= 1.0
    assert "ensemble" in res.model_version
