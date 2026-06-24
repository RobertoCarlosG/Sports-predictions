"""Integration tests for /api/v1/admin/* endpoints.

admin_client uses Bearer token auth (more reliable than cookie persistence with
ASGITransport). Unit tests in test_routes_admin_auth.py cover cookie auth specifically.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.mock_data import (
    ADMIN_HEADERS,
    ADMIN_LOGIN_BODY,
    ADMIN_USERNAME,
    make_admin_user_kwargs,
)
from tests.integration.mock_data_fail import (
    MISSING_PASSWORD_LOGIN_BODY,
    MISSING_USERNAME_LOGIN_BODY,
    NONEXISTENT_USER_LOGIN_BODY,
    PAGINATION_LIMIT_TOO_HIGH,
    PAGINATION_LIMIT_ZERO,
    PAGINATION_NEGATIVE_OFFSET,
    REBUILD_SNAPSHOTS_WINDOW_TOO_LARGE,
    REBUILD_SNAPSHOTS_WINDOW_ZERO,
    WRONG_PASSWORD_LOGIN_BODY,
)

# ---------------------------------------------------------------------------
# GET /api/v1/admin/auth/ready (no auth required)
# ---------------------------------------------------------------------------


async def test_admin_ready_returns_200(client: AsyncClient) -> None:
    r = await client.get("/api/v1/admin/auth/ready")
    assert r.status_code == 200
    body = r.json()
    assert "login_available" in body
    assert "jwt_configured" in body
    assert "admin_table_reachable" in body


async def test_admin_ready_jwt_configured(client: AsyncClient) -> None:
    """JWT is configured in the client fixture."""
    r = await client.get("/api/v1/admin/auth/ready")
    assert r.status_code == 200
    assert r.json()["jwt_configured"] is True


# ---------------------------------------------------------------------------
# POST /api/v1/admin/auth/login — login tests use client (no pre-auth)
# ---------------------------------------------------------------------------


async def test_admin_login_success(client: AsyncClient, db_session: AsyncSession) -> None:
    """Login with correct credentials returns 200."""
    from app.models.mlb import AdminUser

    db_session.add(AdminUser(**make_admin_user_kwargs()))
    await db_session.flush()

    r = await client.post("/api/v1/admin/auth/login", json=ADMIN_LOGIN_BODY, headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == ADMIN_USERNAME
    assert "token_expires_at" in body


async def test_admin_login_wrong_password_returns_401(client: AsyncClient, db_session: AsyncSession) -> None:
    from app.models.mlb import AdminUser

    db_session.add(AdminUser(**make_admin_user_kwargs()))
    await db_session.flush()

    r = await client.post("/api/v1/admin/auth/login", json=WRONG_PASSWORD_LOGIN_BODY, headers=ADMIN_HEADERS)
    assert r.status_code == 401


async def test_admin_login_nonexistent_user_returns_401(client: AsyncClient) -> None:
    r = await client.post("/api/v1/admin/auth/login", json=NONEXISTENT_USER_LOGIN_BODY, headers=ADMIN_HEADERS)
    assert r.status_code == 401


async def test_admin_login_missing_password_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/v1/admin/auth/login", json=MISSING_PASSWORD_LOGIN_BODY, headers=ADMIN_HEADERS)
    assert r.status_code == 422


async def test_admin_login_missing_username_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/v1/admin/auth/login", json=MISSING_USERNAME_LOGIN_BODY, headers=ADMIN_HEADERS)
    assert r.status_code == 422


async def test_admin_login_without_csrf_header_returns_rate_limit_or_auth_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The login endpoint does not check CSRF (only protected endpoints do).
    Without any admin user in DB → 401 (not 403).
    """
    r = await client.post(
        "/api/v1/admin/auth/login",
        json=NONEXISTENT_USER_LOGIN_BODY,
        headers={"Content-Type": "application/json"},  # no X-Requested-With
    )
    # Login endpoint itself has no CSRF check — returns 401 (user not found)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST to protected endpoint without CSRF → 403 (cookie-based only)
# ---------------------------------------------------------------------------


async def test_protected_post_without_csrf_and_with_cookie_returns_403(client: AsyncClient) -> None:
    """CSRF protection applies to cookie-based POST to protected admin endpoints.
    Passes the cookie directly in the request (most reliable with ASGITransport).
    """
    from app.core.admin_security import create_access_token
    from app.core.config import settings

    token = create_access_token(
        secret=settings.admin_jwt_secret,
        subject=ADMIN_USERNAME,
        expire_minutes=settings.admin_token_expire_minutes,
    )

    # POST without X-Requested-With but WITH the cookie → 403 (CSRF protection)
    r = await client.post(
        "/api/v1/admin/auth/refresh",
        headers={"Content-Type": "application/json"},
        cookies={settings.admin_cookie_name: token},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/v1/admin/auth/me — requires auth
# ---------------------------------------------------------------------------


async def test_admin_me_unauthenticated_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/admin/auth/me", headers=ADMIN_HEADERS)
    assert r.status_code == 401


async def test_admin_me_returns_username(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/auth/me", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["username"] == ADMIN_USERNAME


# ---------------------------------------------------------------------------
# POST /api/v1/admin/auth/logout
# ---------------------------------------------------------------------------


async def test_admin_logout_returns_200(admin_client: AsyncClient) -> None:
    r = await admin_client.post("/api/v1/admin/auth/logout", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert "cerrada" in r.json()["message"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/admin/auth/refresh
# ---------------------------------------------------------------------------


async def test_admin_refresh_returns_new_token(admin_client: AsyncClient) -> None:
    r = await admin_client.post("/api/v1/admin/auth/refresh", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert "token_expires_at" in r.json()


# ---------------------------------------------------------------------------
# GET /api/v1/admin/status
# ---------------------------------------------------------------------------


async def test_admin_status_returns_model_info(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/status", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert "message" in r.json()


async def test_admin_status_unauthenticated_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/v1/admin/status", headers=ADMIN_HEADERS)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/admin/pipeline/clear-prediction-cache
# ---------------------------------------------------------------------------


async def test_clear_prediction_cache_returns_success(admin_client: AsyncClient) -> None:
    r = await admin_client.post("/api/v1/admin/pipeline/clear-prediction-cache", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "vaciada" in body["message"].lower() or "eliminadas" in body.get("detail", "").lower()


async def test_clear_cache_unauthenticated_returns_401(client: AsyncClient) -> None:
    r = await client.post("/api/v1/admin/pipeline/clear-prediction-cache", headers=ADMIN_HEADERS)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/admin/pipeline/rebuild-snapshots
# ---------------------------------------------------------------------------


async def test_rebuild_snapshots_returns_success(admin_client: AsyncClient) -> None:
    r = await admin_client.post(
        "/api/v1/admin/pipeline/rebuild-snapshots",
        json={"season": "2025", "window": 10},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert "recalculados" in r.json()["message"].lower()


async def test_rebuild_snapshots_window_zero_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.post(
        "/api/v1/admin/pipeline/rebuild-snapshots",
        json=REBUILD_SNAPSHOTS_WINDOW_ZERO,
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


async def test_rebuild_snapshots_window_too_large_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.post(
        "/api/v1/admin/pipeline/rebuild-snapshots",
        json=REBUILD_SNAPSHOTS_WINDOW_TOO_LARGE,
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


async def test_rebuild_snapshots_with_date_range_returns_success(admin_client: AsyncClient) -> None:
    r = await admin_client.post(
        "/api/v1/admin/pipeline/rebuild-snapshots",
        json={"start_date": "2025-04-01", "end_date": "2025-04-30", "window": 10},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert "recalculados" in r.json()["message"].lower()


async def test_rebuild_snapshots_invalid_date_format_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.post(
        "/api/v1/admin/pipeline/rebuild-snapshots",
        json={"start_date": "01-04-2025", "end_date": "30-04-2025"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


async def test_rebuild_snapshots_no_body_uses_all_dates(admin_client: AsyncClient) -> None:
    r = await admin_client.post(
        "/api/v1/admin/pipeline/rebuild-snapshots",
        json={},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert "recalculados" in r.json()["message"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/admin/model/versions
# ---------------------------------------------------------------------------


async def test_model_versions_returns_paginated_list(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/model/versions", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


async def test_model_versions_limit_zero_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.get(
        "/api/v1/admin/model/versions",
        params=PAGINATION_LIMIT_ZERO,
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


async def test_model_versions_limit_too_high_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.get(
        "/api/v1/admin/model/versions",
        params=PAGINATION_LIMIT_TOO_HIGH,
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


async def test_model_versions_negative_offset_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.get(
        "/api/v1/admin/model/versions",
        params=PAGINATION_NEGATIVE_OFFSET,
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/admin/predictions/metrics
# ---------------------------------------------------------------------------


async def test_prediction_metrics_returns_stats(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/predictions/metrics", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "total_predictions" in body
    assert body["total_predictions"] >= 0


# ---------------------------------------------------------------------------
# GET /api/v1/admin/predictions/backtest
# ---------------------------------------------------------------------------


async def test_backtest_default_params_returns_200(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/predictions/backtest", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "timeseries" in body
    assert "games" in body


async def test_backtest_confidence_below_half_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.get(
        "/api/v1/admin/predictions/backtest",
        params={"min_confidence": 0.49},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


async def test_backtest_confidence_above_one_returns_422(admin_client: AsyncClient) -> None:
    r = await admin_client.get(
        "/api/v1/admin/predictions/backtest",
        params={"min_confidence": 1.01},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/admin/predictions/evaluations
# ---------------------------------------------------------------------------


async def test_evaluations_returns_paginated_list(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/predictions/evaluations", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


# ---------------------------------------------------------------------------
# GET /api/v1/admin/pipeline/backfill-status
# ---------------------------------------------------------------------------


async def test_backfill_status_returns_state(admin_client: AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/pipeline/backfill-status", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert body["status"] in ("idle", "running", "done", "error", "cancelled")


# ---------------------------------------------------------------------------
# POST /api/v1/admin/predictions/evaluate-pending
# ---------------------------------------------------------------------------


async def test_evaluate_pending_returns_200(admin_client: AsyncClient) -> None:
    r = await admin_client.post("/api/v1/admin/predictions/evaluate-pending", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert "message" in r.json()


# ---------------------------------------------------------------------------
# POST /api/v1/admin/predictions/recompute-ml-evaluations
# ---------------------------------------------------------------------------


async def test_recompute_evaluations_returns_200(admin_client: AsyncClient) -> None:
    r = await admin_client.post("/api/v1/admin/predictions/recompute-ml-evaluations", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert "message" in r.json()


# ---------------------------------------------------------------------------
# POST /api/v1/admin/model/reload
# ---------------------------------------------------------------------------


async def test_model_reload_returns_success(admin_client: AsyncClient) -> None:
    r = await admin_client.post("/api/v1/admin/model/reload", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert "recargado" in body["message"].lower()
