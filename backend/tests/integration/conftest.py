"""Integration test infrastructure.

Each async fixture creates its own engine, keeping event-loop bindings clean.
No shared engine across event-loop boundaries.

To start the test DB:
    docker compose up db_test -d

To run integration tests:
    .venv/Scripts/pytest tests/integration/ -v
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.ml.predictor import MlbPredictionService
from app.ml.training import train_default_model
from app.services.admin_backfill_state import initial_backfill_job_state

# Mirror the constants used in the client fixture
from tests.integration.mock_data import ADMIN_JWT_SECRET  # noqa: E402

# ---------------------------------------------------------------------------
# DB URL
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sports_test:sports_test@localhost:5433/sports_test",
)


def _make_engine() -> Any:
    """Create a fresh async engine. Must be used and disposed within one event loop."""
    return create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_size=2,
        max_overflow=0,
    )


def _run(coro: Any) -> Any:
    """Run a coroutine in a brand-new event loop (safe from sync context)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            # Drain any pending tasks before closing
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        finally:
            loop.close()


def _is_db_available() -> bool:
    async def _ping() -> None:
        engine = _make_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    try:
        _run(_ping())
        return True
    except Exception:
        return False


db_available = _is_db_available()

pytestmark = pytest.mark.skipif(
    not db_available,
    reason="PostgreSQL test DB not reachable — start with: docker compose up db_test -d",
)

# ---------------------------------------------------------------------------
# Schema setup — sync, isolated event loop, no engine retained
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def create_schema() -> Iterator[None]:
    """Create all ORM tables once per session."""
    import app.models.bets  # noqa: F401 — registers metadata
    import app.models.mlb  # noqa: F401
    import app.models.nba  # noqa: F401

    async def _setup() -> None:
        engine = _make_engine()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await engine.dispose()

    async def _teardown() -> None:
        engine = _make_engine()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
        finally:
            await engine.dispose()

    _run(_setup())
    yield
    _run(_teardown())


# ---------------------------------------------------------------------------
# Per-test isolation — fresh engine per truncate call
# ---------------------------------------------------------------------------

_TABLE_NAMES = None


def _get_table_names() -> str:
    global _TABLE_NAMES
    if _TABLE_NAMES is None:
        import app.models.bets  # noqa
        import app.models.mlb  # noqa
        import app.models.nba  # noqa

        _TABLE_NAMES = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    return _TABLE_NAMES


@pytest.fixture(autouse=True)
async def truncate_between_tests() -> AsyncIterator[None]:
    """Truncate all tables before each test; owns its own engine."""
    engine = _make_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE TABLE {_get_table_names()} RESTART IDENTITY CASCADE"))
    finally:
        await engine.dispose()
    yield


# ---------------------------------------------------------------------------
# Per-test DB session — fresh engine bound to pytest's event loop
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session using a freshly created engine (no cross-loop contamination)."""
    engine = _make_engine()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------


async def seed_base_data(session: AsyncSession) -> None:
    from app.models.mlb import Game, GameFeatureSnapshot, GameWeather, Team
    from tests.integration.mock_data import ALL_GAMES, ALL_SNAPSHOTS, ALL_TEAMS, ALL_WEATHER

    for t in ALL_TEAMS:
        session.add(Team(**t))
    await session.flush()

    for g in ALL_GAMES:
        session.add(Game(**g))
    await session.flush()

    for w in ALL_WEATHER:
        session.add(GameWeather(**w))
    await session.flush()

    for s in ALL_SNAPSHOTS:
        session.add(GameFeatureSnapshot(**s))

    await session.commit()


# ---------------------------------------------------------------------------
# ML model fixtures (session-scoped, sync — no async needed)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rf_model_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    p = tmp_path_factory.mktemp("models") / "model.joblib"
    train_default_model(p)
    return p


@pytest.fixture(scope="session")
def xgb_model_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    import joblib
    import numpy as np
    from xgboost import XGBClassifier, XGBRegressor

    from app.ml.features import FEATURE_NAMES

    p = tmp_path_factory.mktemp("models") / "model_xgb.joblib"
    rng = np.random.default_rng(42)
    n = 60
    x = rng.normal(size=(n, len(FEATURE_NAMES)))
    y_c = (x[:, 0] > 0).astype(int)
    y_r = rng.uniform(4.0, 12.0, size=n)
    clf = XGBClassifier(n_estimators=4, max_depth=3, random_state=42, eval_metric="logloss")
    reg = XGBRegressor(n_estimators=4, max_depth=3, random_state=42)
    clf.fit(x, y_c)
    reg.fit(x, y_r)
    joblib.dump(
        {
            "clf": clf,
            "reg": reg,
            "model_version": "xgb-integration-v0",
            "feature_names": FEATURE_NAMES,
        },
        p,
    )
    return p


# ---------------------------------------------------------------------------
# ASGI client — real app + fresh session
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(
    db_session: AsyncSession,
    rf_model_path: Path,
    xgb_model_path: Path,
) -> AsyncIterator[AsyncClient]:
    """Full ASGI client: real PostgreSQL, real models, no mocks.

    ASGITransport does NOT trigger the app lifespan, so we set the required
    app.state attributes manually here.
    """
    from app.core.config import settings

    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    await seed_base_data(db_session)

    app.dependency_overrides[get_db] = _get_db_override

    rf_svc = MlbPredictionService(rf_model_path)
    xgb_svc = MlbPredictionService(xgb_model_path)

    # Capture originals
    orig_rf = getattr(app.state, "prediction_service", None)
    orig_xgb = getattr(app.state, "prediction_service_xgb", None)
    orig_active = getattr(app.state, "active_model_version", "")
    orig_http_client = getattr(app.state, "http_client", None)
    orig_inflight = getattr(app.state, "games_list_inflight", None)
    orig_backfill = getattr(app.state, "backfill_job", None)
    orig_admin_secret = settings.admin_jwt_secret
    orig_user_secret = settings.user_jwt_secret

    # Set state that the lifespan would normally set
    app.state.prediction_service = rf_svc
    app.state.prediction_service_xgb = xgb_svc
    app.state.active_model_version = xgb_svc.model_version
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    app.state.games_list_inflight = {}
    app.state.backfill_job = initial_backfill_job_state()

    # Ensure JWT secrets are configured so routes return 401/403 (not 503)
    settings.admin_jwt_secret = ADMIN_JWT_SECRET
    settings.user_jwt_secret = "integration_user_jwt_secret_minimum_32_chars_ok"

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)
        await app.state.http_client.aclose()
        app.state.prediction_service = orig_rf
        app.state.prediction_service_xgb = orig_xgb
        app.state.active_model_version = orig_active
        app.state.http_client = orig_http_client
        app.state.games_list_inflight = orig_inflight
        app.state.backfill_job = orig_backfill
        settings.admin_jwt_secret = orig_admin_secret
        settings.user_jwt_secret = orig_user_secret


# ---------------------------------------------------------------------------
# Admin-authenticated client
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_client(
    client: AsyncClient,
    db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    """Client pre-authenticated as admin using Bearer token.

    Uses Bearer token directly instead of cookies because cookie persistence
    with ASGITransport can be unreliable across request boundaries.
    Unit tests in test_routes_admin_auth.py cover cookie-based auth.
    """
    from app.core.admin_security import create_access_token
    from app.core.config import settings
    from app.models.mlb import AdminUser
    from tests.integration.mock_data import ADMIN_HEADERS, ADMIN_USERNAME, make_admin_user_kwargs

    # admin_jwt_secret is already set in the client fixture
    token = create_access_token(
        secret=settings.admin_jwt_secret,
        subject=ADMIN_USERNAME,
        expire_minutes=settings.admin_token_expire_minutes,
    )

    # Insert admin user so DB queries for admin can find them
    db_session.add(AdminUser(**make_admin_user_kwargs()))
    await db_session.flush()

    client.headers.update({"Authorization": f"Bearer {token}", **ADMIN_HEADERS})
    try:
        yield client
    finally:
        client.headers.pop("Authorization", None)


# ---------------------------------------------------------------------------
# User-authenticated client
# ---------------------------------------------------------------------------


@pytest.fixture
async def user_client(
    client: AsyncClient,
    db_session: AsyncSession,
) -> AsyncIterator[AsyncClient]:
    from app.core.admin_security import create_access_token
    from app.core.config import settings
    from app.models.bets import AppUser
    from tests.integration.mock_data import APP_USER_UUID, make_app_user_kwargs

    # user_jwt_secret is already set in the client fixture — reuse it
    user_jwt = settings.user_jwt_secret
    original_secret = settings.user_jwt_secret

    db_session.add(AppUser(**make_app_user_kwargs()))
    await db_session.flush()

    try:
        token = create_access_token(
            secret=user_jwt,
            subject=str(APP_USER_UUID),
            expire_minutes=settings.user_token_expire_minutes,
        )
        # Set both Bearer header (for bets routes using require_user_id)
        # and the session cookie (for /auth/me which reads cookie directly)
        client.headers.update({"Authorization": f"Bearer {token}"})
        client.cookies.set(settings.user_cookie_name, token, domain="test", path="/")
        yield client
    finally:
        settings.user_jwt_secret = original_secret
        client.headers.pop("Authorization", None)
        with contextlib.suppress(Exception):
            client.cookies.delete(settings.user_cookie_name, domain="test", path="/")


# ---------------------------------------------------------------------------
# Rate limit clearing
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_rate_limits() -> None:
    from app.api import deps_rate_limit

    deps_rate_limit._api_rate_limits_read.clear()
    deps_rate_limit._api_rate_limits_write.clear()
    yield
    deps_rate_limit._api_rate_limits_read.clear()
    deps_rate_limit._api_rate_limits_write.clear()
