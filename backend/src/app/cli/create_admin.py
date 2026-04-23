"""Crea un usuario del panel de operaciones (tabla admin_users).

Uso (desde el directorio backend/, con DATABASE_URL):

  python -m app.cli.create_admin --username admin --password 'secreto-seguro'

Requiere haber aplicado sql/002_prediction_cache_and_admin.sql.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.core.admin_security import hash_password
from app.db.session import async_session_factory
from app.models.mlb import AdminUser

log = logging.getLogger(__name__)


async def _run(username: str, password: str) -> None:
    async with async_session_factory() as session:
        existing = await session.execute(select(AdminUser).where(AdminUser.username == username))
        if existing.scalar_one_or_none() is not None:
            log.error("El usuario %s ya existe.", username)
            raise SystemExit(1)
        session.add(
            AdminUser(
                username=username,
                password_hash=hash_password(password),
                is_active=True,
            )
        )
        await session.commit()
    log.info("Usuario administrativo '%s' creado.", username)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Create admin_users row for the operations panel.")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    args = p.parse_args(argv)
    asyncio.run(_run(args.username, args.password))


if __name__ == "__main__":
    main()
