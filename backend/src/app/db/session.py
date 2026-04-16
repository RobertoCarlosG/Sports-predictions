from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# PgBouncer (Supabase/Render) en modo transacción + SQLAlchemy asyncpg:
# 1) `statement_cache_size=0` solo afecta la caché interna de asyncpg.
# 2) El dialecto de SQLAlchemy usa su propia caché (`prepared_statement_cache_size`,
#    por defecto 100) vía connection.prepare(); hay que ponerla a 0 en la URL:
#    https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#prepared-statement-cache
# 3) Nombres de statement únicos evitan colisiones tras reasignar backend (doc dialecto).
_engine_url = make_url(settings.database_url).update_query_dict(
    {"prepared_statement_cache_size": "0"},
)
engine = create_async_engine(
    _engine_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4().hex}__",
    },
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
