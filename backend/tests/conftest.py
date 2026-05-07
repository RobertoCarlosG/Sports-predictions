"""Fixtures compartidos: SQLite en memoria + override de ``get_db`` para tests de API admin."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db


@pytest.fixture(autouse=True)
def clear_admin_login_rate_limit() -> None:
    """Evita que intentos fallidos de tests anteriores disparen 429 en el siguiente test."""
    from app.api.routes import admin as admin_routes

    admin_routes._login_attempts.clear()
    yield
    admin_routes._login_attempts.clear()


@pytest.fixture
async def sqlite_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def sqlite_session_factory(sqlite_engine):
    return async_sessionmaker(
        sqlite_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def override_app_db(sqlite_session_factory, monkeypatch):
    """Sustituye ``get_db`` del ``app`` por sesiones SQLite (misma transacción = mismo motor)."""

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with sqlite_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from app.main import app

    app.dependency_overrides[get_db] = _override_get_db
    yield
    del app.dependency_overrides[get_db]
