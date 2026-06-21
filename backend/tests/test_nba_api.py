"""Tests HTTP de rutas /api/v1/nba/* con get_db en SQLite y modelo NBA cargado."""

from __future__ import annotations

import argparse
import datetime as dt

import joblib
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.ml.train_nba_from_db import _build_models
from app.models.nba import NbaGame, NbaGameFeatureSnapshot, NbaTeam


def _make_model(path):
    ns = argparse.Namespace(
        trees=20, max_depth=3, learning_rate=0.1, subsample=0.9, colsample_bytree=0.9
    )
    rng = np.random.default_rng(0)
    x = rng.random((80, 18))
    yh = (x[:, 6] > x[:, 7]).astype(int)
    ym = (x[:, 6] - x[:, 7]) * 10
    yt = x[:, 2] + x[:, 3] + 200
    clf, rm, rt = _build_models("xgb", ns)
    clf.fit(x, yh)
    rm.fit(x, ym)
    rt.fit(x, yt)
    joblib.dump(
        {
            "clf": clf,
            "reg_margin": rm,
            "reg_total": rt,
            "feature_names": [f"f{i}" for i in range(18)],
            "model_version": "nba-xgb-test",
        },
        path,
    )


@pytest.fixture
async def nba_model(tmp_path, monkeypatch):
    from app.ml.nba_predictor import NbaPredictionService

    path = tmp_path / "model_nba_xgb.joblib"
    _make_model(path)
    monkeypatch.setattr(
        app.state, "nba_prediction_service_xgb", NbaPredictionService(path), raising=False
    )
    monkeypatch.setattr(app.state, "nba_prediction_service_lgbm", None, raising=False)
    monkeypatch.setattr(app.state, "nba_prediction_service_catboost", None, raising=False)
    yield


@pytest.fixture
async def client(override_app_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


async def _seed(session):
    session.add(NbaTeam(id=1, name="Alpha", abbreviation="ALP"))
    session.add(NbaTeam(id=2, name="Bravo", abbreviation="BRV"))
    session.add(
        NbaGame(
            game_id="0022300001",
            season="2023-24",
            game_date=dt.date(2024, 1, 15),
            status="Final",
            home_team_id=1,
            away_team_id=2,
            home_score=112,
            away_score=104,
        )
    )
    session.add(
        NbaGameFeatureSnapshot(
            game_id="0022300001",
            home_win_pct_roll=0.6,
            away_win_pct_roll=0.4,
            home_pts_for_roll=114.0,
            away_pts_for_roll=108.0,
            home_pts_against_roll=106.0,
            away_pts_against_roll=110.0,
            home_net_rating_roll=6.0,
            away_net_rating_roll=-2.0,
            home_pace_roll=100.0,
            away_pace_roll=99.0,
            home_efg_roll=0.55,
            away_efg_roll=0.52,
            home_rest_days=2,
            away_rest_days=1,
            home_is_b2b=0,
            away_is_b2b=1,
            home_win=1,
            margin=8.0,
            total_points=216.0,
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_list_teams(client, sqlite_session_factory):
    async with sqlite_session_factory() as s:
        await _seed(s)
        await s.commit()
    r = await client.get("/api/v1/nba/teams")
    assert r.status_code == 200
    abbrs = {t["abbreviation"] for t in r.json()}
    assert {"ALP", "BRV"} <= abbrs


@pytest.mark.asyncio
async def test_predict_returns_markets(client, sqlite_session_factory, nba_model):
    async with sqlite_session_factory() as s:
        await _seed(s)
        await s.commit()
    r = await client.get("/api/v1/nba/predict/0022300001")
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["home_win_probability"] <= 1.0
    assert "total_points_estimate" in body
    assert "spread_line" in body
    assert body["model_version"].startswith("nba-xgb-test")


@pytest.mark.asyncio
async def test_predict_unavailable_model_returns_503(client, sqlite_session_factory, nba_model):
    async with sqlite_session_factory() as s:
        await _seed(s)
        await s.commit()
    r = await client.get("/api/v1/nba/predict/0022300001?model=lgbm")
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_get_game_includes_prediction(client, sqlite_session_factory, nba_model):
    async with sqlite_session_factory() as s:
        await _seed(s)
        await s.commit()
    r = await client.get("/api/v1/nba/games/0022300001")
    assert r.status_code == 200
    body = r.json()
    assert body["home_team"]["abbreviation"] == "ALP"
    assert body["prediction"] is not None


@pytest.mark.asyncio
async def test_get_game_not_found(client):
    r = await client.get("/api/v1/nba/games/does-not-exist")
    assert r.status_code == 404
