"""Integration tests for /api/v1/predict/* endpoints.

Tests both RF and XGBoost prediction paths using real model files
and real DB data — no MagicMock.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.mock_data import FINAL_HOME_WIN_PK, SCHEDULED_GAME_PK
from tests.integration.mock_data_fail import NONEXISTENT_GAME_PK

# ---------------------------------------------------------------------------
# GET /api/v1/predict/{game_pk} — RF model (default)
# ---------------------------------------------------------------------------


async def test_predict_rf_returns_valid_probability(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=rf")
    assert r.status_code == 200
    body = r.json()
    assert body["game_pk"] == SCHEDULED_GAME_PK
    assert 0.0 <= body["home_win_probability"] <= 1.0
    assert body["total_runs_estimate"] > 0.0
    assert body["over_under_line"] > 0.0
    assert body["model_version"] is not None
    assert body["predicted_winner"] in ("home", "away")


async def test_predict_rf_response_has_asian_handicap(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=rf")
    assert r.status_code == 200
    body = r.json()
    ah = body.get("asian_handicap")
    assert ah is not None
    assert "home" in ah and "away" in ah
    assert ah["home"]["team_abbr"] == "LAD"
    assert ah["away"]["team_abbr"] == "NYY"
    assert 0.0 <= ah["home"]["cover_probability"] <= 1.0


async def test_predict_xgb_default_model_param(client: AsyncClient) -> None:
    # No ?model= query → defaults to xgb
    r = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}")
    assert r.status_code == 200
    body = r.json()
    assert "home_win_probability" in body
    assert "xgb" in body["model_version"]


async def test_predict_rf_final_game_returns_prediction(client: AsyncClient) -> None:
    # Prediction works even for completed games
    r = await client.get(f"/api/v1/predict/{FINAL_HOME_WIN_PK}?model=rf")
    assert r.status_code == 200
    assert 0.0 <= r.json()["home_win_probability"] <= 1.0


async def test_predict_second_call_returns_cached_response(client: AsyncClient) -> None:
    r1 = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=rf")
    r2 = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=rf")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same model_version → cached response (same values)
    assert r1.json()["home_win_probability"] == r2.json()["home_win_probability"]


# ---------------------------------------------------------------------------
# GET /api/v1/predict/{game_pk} — XGBoost model
# ---------------------------------------------------------------------------


async def test_predict_xgb_returns_valid_probability(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=xgb")
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["home_win_probability"] <= 1.0
    assert body["model_version"].startswith("xgb-integration-v0@")


async def test_predict_xgb_response_has_asian_handicap(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=xgb")
    assert r.status_code == 200
    assert r.json().get("asian_handicap") is not None


async def test_predict_xgb_model_version_differs_from_rf(client: AsyncClient) -> None:
    r_rf = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=rf")
    r_xgb = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=xgb")
    assert r_rf.status_code == 200
    assert r_xgb.status_code == 200
    assert r_rf.json()["model_version"] != r_xgb.json()["model_version"]


# ---------------------------------------------------------------------------
# GET /api/v1/predict/{game_pk} — failure cases
# ---------------------------------------------------------------------------


async def test_predict_game_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/predict/{NONEXISTENT_GAME_PK}?model=rf")
    assert r.status_code == 404


async def test_predict_invalid_pk_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/predict/not-a-number")
    assert r.status_code == 422


async def test_predict_invalid_model_param_returns_422(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=gradient_boosting")
    assert r.status_code == 422


async def test_predict_xgb_unavailable_when_not_loaded(client: AsyncClient) -> None:
    from app.main import app

    orig = app.state.prediction_service_xgb
    app.state.prediction_service_xgb = None
    try:
        r = await client.get(f"/api/v1/predict/{SCHEDULED_GAME_PK}?model=xgb")
        assert r.status_code == 503
        assert "XGBoost" in r.json()["detail"]
    finally:
        app.state.prediction_service_xgb = orig


# ---------------------------------------------------------------------------
# POST /api/v1/predict/{game_pk}/refresh
# ---------------------------------------------------------------------------


async def test_refresh_prediction_rf_returns_200(client: AsyncClient) -> None:
    r = await client.post(f"/api/v1/predict/{SCHEDULED_GAME_PK}/refresh?model=rf")
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["home_win_probability"] <= 1.0


async def test_refresh_prediction_xgb_returns_200(client: AsyncClient) -> None:
    r = await client.post(f"/api/v1/predict/{SCHEDULED_GAME_PK}/refresh?model=xgb")
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"].startswith("xgb-integration-v0@")


async def test_refresh_prediction_game_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.post(f"/api/v1/predict/{NONEXISTENT_GAME_PK}/refresh?model=rf")
    assert r.status_code == 404


async def test_refresh_prediction_xgb_unavailable_returns_503(client: AsyncClient) -> None:
    from app.main import app

    orig = app.state.prediction_service_xgb
    app.state.prediction_service_xgb = None
    try:
        r = await client.post(f"/api/v1/predict/{SCHEDULED_GAME_PK}/refresh?model=xgb")
        assert r.status_code == 503
    finally:
        app.state.prediction_service_xgb = orig
