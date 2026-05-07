"""Tests de ``login_with_password`` contra SQLite en memoria."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.admin_security import hash_password
from app.core.config import settings
from app.db.base import Base
from app.models.mlb import AdminUser
from app.services.admin_auth import AdminAuthError, login_with_password

_JWT_UNIT = "unit_test_jwt_secret_minimum_20_characters"


@pytest.fixture
async def auth_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_login_success(monkeypatch, auth_session: AsyncSession) -> None:
    monkeypatch.setattr(settings, "admin_jwt_secret", _JWT_UNIT, raising=False)
    auth_session.add(
        AdminUser(
            username="carol",
            password_hash=hash_password("secret-pass"),
            is_active=True,
        )
    )
    await auth_session.commit()

    user, token = await login_with_password("carol", "secret-pass", auth_session)
    assert user == "carol"
    assert isinstance(token, str) and len(token) > 20


@pytest.mark.asyncio
async def test_login_wrong_password(monkeypatch, auth_session: AsyncSession) -> None:
    monkeypatch.setattr(settings, "admin_jwt_secret", _JWT_UNIT, raising=False)
    auth_session.add(
        AdminUser(
            username="dave",
            password_hash=hash_password("good"),
            is_active=True,
        )
    )
    await auth_session.commit()

    with pytest.raises(AdminAuthError):
        await login_with_password("dave", "bad", auth_session)


@pytest.mark.asyncio
async def test_login_inactive_user(monkeypatch, auth_session: AsyncSession) -> None:
    monkeypatch.setattr(settings, "admin_jwt_secret", _JWT_UNIT, raising=False)
    auth_session.add(
        AdminUser(
            username="eve",
            password_hash=hash_password("x"),
            is_active=False,
        )
    )
    await auth_session.commit()

    with pytest.raises(AdminAuthError):
        await login_with_password("eve", "x", auth_session)


@pytest.mark.asyncio
async def test_login_without_jwt_secret(monkeypatch, auth_session: AsyncSession) -> None:
    monkeypatch.setattr(settings, "admin_jwt_secret", "", raising=False)
    auth_session.add(
        AdminUser(
            username="nojwt",
            password_hash=hash_password("x"),
            is_active=True,
        )
    )
    await auth_session.commit()

    with pytest.raises(AdminAuthError, match="ADMIN_JWT_SECRET"):
        await login_with_password("nojwt", "x", auth_session)
