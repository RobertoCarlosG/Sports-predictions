from sqlalchemy.engine import make_url

from app.db.db_url import build_asyncpg_engine_params


def test_build_asyncpg_engine_params_no_force_unchanged_host() -> None:
    url, extras = build_asyncpg_engine_params(
        "postgresql+asyncpg://user:pass@localhost:5432/mydb",
        force_ipv4=False,
    )
    assert make_url(str(url)).host == "localhost"
    assert extras == {}


def test_build_asyncpg_engine_params_literal_ip_skips_resolve() -> None:
    url, extras = build_asyncpg_engine_params(
        "postgresql+asyncpg://user:pass@127.0.0.1:5432/mydb",
        force_ipv4=True,
    )
    assert make_url(str(url)).host == "127.0.0.1"
    assert extras == {}
