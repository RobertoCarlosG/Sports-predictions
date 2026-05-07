"""Tests HTTP de rutas ``/api/v1/admin/auth/*`` con ``get_db`` en SQLite."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.admin_security import create_access_token, hash_password
from app.core.config import settings
from app.main import app
from app.models.mlb import AdminUser

ADMIN_JWT = "unit_test_jwt_secret_for_tests_minimum_24_chars"
ADMIN_HEADERS_JSON = {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"}


@pytest.fixture
def patch_admin_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_jwt_secret", ADMIN_JWT, raising=False)
    monkeypatch.setattr(settings, "admin_bootstrap_secret", "", raising=False)


@pytest.fixture
async def client(patch_admin_settings, sqlite_session_factory, override_app_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_auth_ready_with_sqlite(client: AsyncClient) -> None:
    r = await client.get("/api/v1/admin/auth/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["jwt_configured"] is True
    assert body["admin_table_reachable"] is True
    assert body["login_available"] is True


@pytest.mark.asyncio
async def test_login_success_inserts_session(
    client: AsyncClient,
    sqlite_session_factory,
) -> None:
    async with sqlite_session_factory() as s:
        s.add(AdminUser(username="op1", password_hash=hash_password("p4ss-w0rd"), is_active=True))
        await s.commit()

    r = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": "op1", "password": "p4ss-w0rd"},
        headers=ADMIN_HEADERS_JSON,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "op1"
    assert "sp_admin_access" in r.cookies or r.cookies.get("sp_admin_access")


@pytest.mark.asyncio
async def test_login_wrong_password_401(
    client: AsyncClient,
    sqlite_session_factory,
) -> None:
    async with sqlite_session_factory() as s:
        s.add(AdminUser(username="op2", password_hash=hash_password("right"), is_active=True))
        await s.commit()

    r = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": "op2", "password": "wrong"},
        headers=ADMIN_HEADERS_JSON,
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_429(
    client: AsyncClient,
    sqlite_session_factory,
) -> None:
    async with sqlite_session_factory() as s:
        s.add(AdminUser(username="op3", password_hash=hash_password("ok"), is_active=True))
        await s.commit()

    for _ in range(5):
        r = await client.post(
            "/api/v1/admin/auth/login",
            json={"username": "op3", "password": "bad"},
            headers=ADMIN_HEADERS_JSON,
        )
        assert r.status_code == 401

    r6 = await client.post(
        "/api/v1/admin/auth/login",
        json={"username": "op3", "password": "bad"},
        headers=ADMIN_HEADERS_JSON,
    )
    assert r6.status_code == 429


@pytest.mark.asyncio
async def test_bootstrap_404_when_secret_disabled(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    sqlite_session_factory,
) -> None:
    monkeypatch.setattr(settings, "admin_bootstrap_secret", "", raising=False)
    r = await client.post(
        "/api/v1/admin/auth/bootstrap",
        json={"username": "new1", "password": "x" * 12},
        headers={**ADMIN_HEADERS_JSON, "X-Admin-Bootstrap-Secret": "anything"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_bootstrap_creates_first_user(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
    sqlite_session_factory,
) -> None:
    monkeypatch.setattr(
        settings,
        "admin_bootstrap_secret",
        "bootstrap_secret_test_value_32chars!!",
        raising=False,
    )
    r = await client.post(
        "/api/v1/admin/auth/bootstrap",
        json={"username": "bootstrap_user", "password": "Str0ng!pw_here"},
        headers={
            **ADMIN_HEADERS_JSON,
            "X-Admin-Bootstrap-Secret": "bootstrap_secret_test_value_32chars!!",
        },
    )
    assert r.status_code == 200
    assert r.json()["username"] == "bootstrap_user"

    r2 = await client.post(
        "/api/v1/admin/auth/bootstrap",
        json={"username": "another", "password": "x" * 12},
        headers={
            **ADMIN_HEADERS_JSON,
            "X-Admin-Bootstrap-Secret": "bootstrap_secret_test_value_32chars!!",
        },
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_refresh_and_me_with_bearer(
    client: AsyncClient,
    sqlite_session_factory,
) -> None:
    async with sqlite_session_factory() as s:
        s.add(AdminUser(username="tok", password_hash=hash_password("x"), is_active=True))
        await s.commit()

    token = create_access_token(
        secret=ADMIN_JWT,
        subject="tok",
        expire_minutes=60,
    )
    auth_h = {"Authorization": f"Bearer {token}"}

    me = await client.get("/api/v1/admin/auth/me", headers=auth_h)
    assert me.status_code == 200
    assert me.json()["username"] == "tok"

    ref = await client.post("/api/v1/admin/auth/refresh", headers=auth_h)
    assert ref.status_code == 200


@pytest.mark.asyncio
async def test_post_me_without_csrf_header_fails_with_cookie_only(
    client: AsyncClient,
    sqlite_session_factory,
) -> None:
    """Mutación con cookie pero sin X-Requested-With debe devolver 403 (CSRF)."""
    async with sqlite_session_factory() as s:
        s.add(AdminUser(username="csrf", password_hash=hash_password("x"), is_active=True))
        await s.commit()

    token = create_access_token(secret=ADMIN_JWT, subject="csrf", expire_minutes=60)
    # Simular cookie sin cabecera anti-CSRF en un POST
    r = await client.post(
        "/api/v1/admin/auth/refresh",
        cookies={"sp_admin_access": token},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_clear_prediction_cache_requires_auth(
    client: AsyncClient,
) -> None:
    r = await client.post("/api/v1/admin/pipeline/clear-prediction-cache")
    assert r.status_code == 401
