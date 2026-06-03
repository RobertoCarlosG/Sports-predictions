"""Tests for app.api.routes.predict — covering both RF and XGBoost model selection,
503 handling, cache logic, error paths, and all major branches."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from httpx import ASGITransport, AsyncClient

from app.api.routes.predict import _get_prediction_service
from app.main import app
from app.schemas.games import AsianHandicapBlock, AsianHandicapSideOut, PredictionResponse


# ---------------------------------------------------------------------------
# Canned response used across tests
# ---------------------------------------------------------------------------

_MOCK_PRED = PredictionResponse(
    game_pk=777,
    home_win_probability=0.62,
    total_runs_estimate=8.7,
    over_under_line=8.5,
    model_version="xgb-test@abc123",
    predicted_winner="home",
    asian_handicap=AsianHandicapBlock(
        home=AsianHandicapSideOut(team_abbr="LAD", line=-0.5, cover_probability=0.58),
        away=AsianHandicapSideOut(team_abbr="NYY", line=0.5, cover_probability=0.42),
    ),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_rate_limits() -> None:
    from app.api import deps_rate_limit

    deps_rate_limit._api_rate_limits_read.clear()
    deps_rate_limit._api_rate_limits_write.clear()
    yield
    deps_rate_limit._api_rate_limits_read.clear()
    deps_rate_limit._api_rate_limits_write.clear()


def _mock_svc(model_version: str = "rf-test@abc") -> MagicMock:
    svc = MagicMock()
    svc.model_version = model_version
    return svc


@pytest.fixture
async def client(override_app_db: Any) -> Any:
    """AsyncClient with SQLite DB override and mock prediction services."""
    mock_rf = _mock_svc("rf-test@abc")
    mock_xgb = _mock_svc("xgb-test@abc")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        orig_rf = getattr(app.state, "prediction_service", None)
        orig_xgb = getattr(app.state, "prediction_service_xgb", None)
        app.state.prediction_service = mock_rf
        app.state.prediction_service_xgb = mock_xgb
        try:
            yield ac
        finally:
            app.state.prediction_service = orig_rf
            app.state.prediction_service_xgb = orig_xgb


# ---------------------------------------------------------------------------
# Unit tests: _get_prediction_service (no HTTP)
# ---------------------------------------------------------------------------

def _mock_request(rf: Any = None, xgb: Any = None) -> MagicMock:
    req = MagicMock(spec=Request)
    req.app.state.prediction_service = rf
    req.app.state.prediction_service_xgb = xgb
    return req


def test_get_service_rf_returns_rf() -> None:
    sentinel = object()
    req = _mock_request(rf=sentinel, xgb=None)
    result = _get_prediction_service(req, model="rf")
    assert result is sentinel


def test_get_service_xgb_returns_xgb() -> None:
    sentinel = object()
    req = _mock_request(rf=None, xgb=sentinel)
    result = _get_prediction_service(req, model="xgb")
    assert result is sentinel


def test_get_service_xgb_none_raises_503() -> None:
    req = _mock_request(rf=_mock_svc(), xgb=None)
    with pytest.raises(HTTPException) as exc_info:
        _get_prediction_service(req, model="xgb")
    assert exc_info.value.status_code == 503
    assert "XGBoost" in exc_info.value.detail


def test_get_service_rf_none_raises_503() -> None:
    req = _mock_request(rf=None, xgb=_mock_svc())
    with pytest.raises(HTTPException) as exc_info:
        _get_prediction_service(req, model="rf")
    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# GET /api/v1/predict/{game_pk} — happy paths
# ---------------------------------------------------------------------------

async def test_get_predict_xgb_200(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.predict.get_cached_prediction",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.api.routes.predict.compute_prediction_response",
        AsyncMock(return_value=_MOCK_PRED),
    )
    monkeypatch.setattr(
        "app.api.routes.predict.upsert_prediction_cache",
        AsyncMock(return_value=None),
    )
    r = await client.get("/api/v1/predict/777?model=xgb")
    assert r.status_code == 200
    assert r.json()["game_pk"] == 777


async def test_get_predict_rf_200(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.predict.get_cached_prediction",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.api.routes.predict.compute_prediction_response",
        AsyncMock(return_value=_MOCK_PRED),
    )
    monkeypatch.setattr(
        "app.api.routes.predict.upsert_prediction_cache",
        AsyncMock(return_value=None),
    )
    r = await client.get("/api/v1/predict/777?model=rf")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/v1/predict/{game_pk} — 503 when service not loaded
# ---------------------------------------------------------------------------

async def test_get_predict_xgb_503_no_service(client: AsyncClient) -> None:
    orig = app.state.prediction_service_xgb
    app.state.prediction_service_xgb = None
    try:
        r = await client.get("/api/v1/predict/777?model=xgb")
    finally:
        app.state.prediction_service_xgb = orig
    assert r.status_code == 503
    assert "XGBoost" in r.json()["detail"]


async def test_get_predict_rf_503_no_service(client: AsyncClient) -> None:
    orig = app.state.prediction_service
    app.state.prediction_service = None
    try:
        r = await client.get("/api/v1/predict/777?model=rf")
    finally:
        app.state.prediction_service = orig
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# GET — active_model_version side-effect
# ---------------------------------------------------------------------------

async def test_get_predict_rf_sets_active_model_version(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.routes.predict.get_cached_prediction", AsyncMock(return_value=None))
    monkeypatch.setattr("app.api.routes.predict.compute_prediction_response", AsyncMock(return_value=_MOCK_PRED))
    monkeypatch.setattr("app.api.routes.predict.upsert_prediction_cache", AsyncMock(return_value=None))
    app.state.prediction_service = _mock_svc("rf-test@abc")
    r = await client.get("/api/v1/predict/777?model=rf")
    assert r.status_code == 200
    assert app.state.active_model_version == "rf-test@abc"


async def test_get_predict_xgb_skips_active_model_version(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.routes.predict.get_cached_prediction", AsyncMock(return_value=None))
    monkeypatch.setattr("app.api.routes.predict.compute_prediction_response", AsyncMock(return_value=_MOCK_PRED))
    monkeypatch.setattr("app.api.routes.predict.upsert_prediction_cache", AsyncMock(return_value=None))
    app.state.active_model_version = "sentinel-version"
    r = await client.get("/api/v1/predict/777?model=xgb")
    assert r.status_code == 200
    assert app.state.active_model_version == "sentinel-version"


# ---------------------------------------------------------------------------
# GET — cache hit path
# ---------------------------------------------------------------------------

async def test_get_predict_cache_hit_skips_compute(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routes.predict.get_cached_prediction",
        AsyncMock(return_value=_MOCK_PRED),  # cache hit
    )
    compute_mock = AsyncMock(side_effect=AssertionError("should not be called"))
    monkeypatch.setattr("app.api.routes.predict.compute_prediction_response", compute_mock)
    r = await client.get("/api/v1/predict/777?model=xgb")
    assert r.status_code == 200
    compute_mock.assert_not_called()


# ---------------------------------------------------------------------------
# GET — error paths
# ---------------------------------------------------------------------------

async def test_get_predict_compute_exception_returns_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.routes.predict.get_cached_prediction", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "app.api.routes.predict.compute_prediction_response",
        AsyncMock(side_effect=ValueError("boom")),
    )
    r = await client.get("/api/v1/predict/777?model=xgb")
    assert r.status_code == 500
    assert "Error al calcular" in r.json()["detail"]


async def test_get_predict_http_exception_reraises(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.routes.predict.get_cached_prediction", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "app.api.routes.predict.compute_prediction_response",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="Game not found")),
    )
    r = await client.get("/api/v1/predict/777?model=xgb")
    assert r.status_code == 404


async def test_get_predict_cache_upsert_failure_still_200(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    monkeypatch.setattr("app.api.routes.predict.get_cached_prediction", AsyncMock(return_value=None))
    monkeypatch.setattr("app.api.routes.predict.compute_prediction_response", AsyncMock(return_value=_MOCK_PRED))
    monkeypatch.setattr(
        "app.api.routes.predict.upsert_prediction_cache",
        AsyncMock(side_effect=Exception("DB down")),
    )
    with caplog.at_level(logging.WARNING, logger="app.api.routes.predict"):
        r = await client.get("/api/v1/predict/777?model=xgb")
    assert r.status_code == 200
    warnings = [rec for rec in caplog.records if rec.levelno >= logging.WARNING]
    assert any("prediction cache upsert failed" in rec.message for rec in warnings)


# ---------------------------------------------------------------------------
# POST /api/v1/predict/{game_pk}/refresh — happy path
# ---------------------------------------------------------------------------

async def test_post_refresh_xgb_200(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.predict.compute_prediction_response", AsyncMock(return_value=_MOCK_PRED))
    monkeypatch.setattr("app.api.routes.predict.upsert_prediction_cache", AsyncMock(return_value=None))
    r = await client.post("/api/v1/predict/777/refresh?model=xgb")
    assert r.status_code == 200


async def test_post_refresh_rf_200(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.predict.compute_prediction_response", AsyncMock(return_value=_MOCK_PRED))
    monkeypatch.setattr("app.api.routes.predict.upsert_prediction_cache", AsyncMock(return_value=None))
    r = await client.post("/api/v1/predict/777/refresh?model=rf")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# POST /refresh — 503 when service not loaded
# ---------------------------------------------------------------------------

async def test_post_refresh_xgb_503(client: AsyncClient) -> None:
    orig = app.state.prediction_service_xgb
    app.state.prediction_service_xgb = None
    try:
        r = await client.post("/api/v1/predict/777/refresh?model=xgb")
    finally:
        app.state.prediction_service_xgb = orig
    assert r.status_code == 503
    assert "XGBoost" in r.json()["detail"]


# ---------------------------------------------------------------------------
# POST /refresh — error paths
# ---------------------------------------------------------------------------

async def test_post_refresh_compute_exception_500(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routes.predict.compute_prediction_response",
        AsyncMock(side_effect=RuntimeError("oops")),
    )
    r = await client.post("/api/v1/predict/777/refresh?model=xgb")
    assert r.status_code == 500
    assert "Error al calcular" in r.json()["detail"]


async def test_post_refresh_http_exception_reraises(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.routes.predict.compute_prediction_response",
        AsyncMock(side_effect=HTTPException(status_code=404, detail="not found")),
    )
    r = await client.post("/api/v1/predict/777/refresh?model=xgb")
    assert r.status_code == 404


async def test_post_refresh_upsert_failure_still_200(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    monkeypatch.setattr("app.api.routes.predict.compute_prediction_response", AsyncMock(return_value=_MOCK_PRED))
    monkeypatch.setattr(
        "app.api.routes.predict.upsert_prediction_cache",
        AsyncMock(side_effect=Exception("DB error")),
    )
    with caplog.at_level(logging.WARNING, logger="app.api.routes.predict"):
        r = await client.post("/api/v1/predict/777/refresh?model=xgb")
    assert r.status_code == 200
    warnings = [rec for rec in caplog.records if rec.levelno >= logging.WARNING]
    assert any("prediction cache upsert failed" in rec.message for rec in warnings)
