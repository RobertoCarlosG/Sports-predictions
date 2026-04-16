"""Ajustes de URL para asyncpg.

Por defecto en producción se usa Supabase **transaction pooler** (IPv4). `force_ipv4` es opcional
si en el futuro usas conexión directa con IPv4 (add-on); no sustituye al pooler en free tier.
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Any

from sqlalchemy.engine.url import URL, make_url


def build_asyncpg_engine_params(
    database_url: str,
    *,
    force_ipv4: bool,
    prepared_statement_cache_size: str = "0",
) -> tuple[URL, dict[str, Any]]:
    """Devuelve URL SQLAlchemy y kwargs extra para connect_args de asyncpg.

    `force_ipv4`: si True, resuelve el hostname a una IPv4 y conecta por IP;
    pasa `server_hostname` al nombre original para que el TLS siga validando el cert.
    Útil cuando el host resuelve primero a IPv6 y el entorno (p. ej. Render) no tiene
    ruta IPv6 (OSError errno 101 Network is unreachable).
    """
    u = make_url(database_url).update_query_dict(
        {"prepared_statement_cache_size": prepared_statement_cache_size}
    )
    extras: dict[str, Any] = {}
    if not force_ipv4 or not u.host:
        return u, extras

    try:
        ipaddress.ip_address(u.host)
        return u, extras
    except ValueError:
        pass

    port = int(u.port or 5432)
    infos = socket.getaddrinfo(u.host, port, socket.AF_INET, socket.SOCK_STREAM)
    if not infos:
        raise OSError(f"No IPv4 address for database host {u.host!r}")
    ipv4 = infos[0][4][0]
    original = u.host
    u = u.set(host=ipv4)
    extras["server_hostname"] = original
    return u, extras
