from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.db_url import build_asyncpg_engine_params

# Objetivo producción: Supabase TRANSACTION POOLER (free tier: direct 5432 no es IPv4-compatible).
# PgBouncer + asyncpg: prepared_statement_cache_size=0, statement_cache_size=0, nombres únicos, NullPool.
# DATABASE_FORCE_IPV4 solo si tu URL directa tiene IPv4 (add-on); con pooler no hace falta.
_engine_url, _ipv4_extras = build_asyncpg_engine_params(
    settings.database_url,
    force_ipv4=settings.database_force_ipv4,
)
_connect_args: dict = {
    "statement_cache_size": 0,
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
    **_ipv4_extras,
}
# Evita QueryCanceledError al persistir JSON grandes (boxscore) si el rol/pooler usa timeout bajo.
if settings.database_statement_timeout_seconds > 0:
    _connect_args.setdefault("server_settings", {}).update(
        {"statement_timeout": f"{settings.database_statement_timeout_seconds}s"},
    )
engine = create_async_engine(
    _engine_url,
    echo=False,
    poolclass=NullPool,
    connect_args=_connect_args,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
