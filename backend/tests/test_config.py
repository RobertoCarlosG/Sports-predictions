from app.core.config import normalize_async_database_url


def test_normalize_postgresql_to_asyncpg() -> None:
    url = "postgresql://user:pass@host:5432/db"
    assert normalize_async_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normalize_postgres_scheme() -> None:
    url = "postgres://user:pass@host:5432/db"
    assert normalize_async_database_url(url) == "postgresql+asyncpg://user:pass@host:5432/db"


def test_normalize_preserves_asyncpg() -> None:
    url = "postgresql+asyncpg://user:pass@host:5432/db"
    assert normalize_async_database_url(url) == url
