from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# PgBouncer (Supabase/Render) en modo transacción + asyncpg:
# - URL: prepared_statement_cache_size=0 (caché del dialecto SQLAlchemy).
# - connect_args: statement_cache_size=0 + nombres únicos (doc asyncpg dialect).
# - NullPool: no reutilizar conexiones en el proceso; si no, el pool devuelve un
#   socket que PgBouncer puede enrutar a otro backend y los prepared statements
#   invalidan (__asyncpg_stmt_*__). Ver docs SQLAlchemy "Prepared Statement Name with PGBouncer".
_engine_url = make_url(settings.database_url).update_query_dict(
    {"prepared_statement_cache_size": "0"},
)
engine = create_async_engine(
    _engine_url,
    echo=False,
    poolclass=NullPool,
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
