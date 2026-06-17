"""Sync incremental: sincroniza hoy y mañana desde MLB API y recalcula solo los
snapshots de esos dos días. Mucho más rápido que daily_snapshot, que reconstruye
toda la temporada.

Cuándo usar cada uno:
  sync_today     → hoy/mañana cambiaron (alineaciones, abridores, estado del partido).
  daily_snapshot → rebuild completo de temporada (primer run, corrección histórica).

Uso (desde `backend/`):

  uv run python -m app.cli.sync_today
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

import httpx

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.feature_snapshots import rebuild_game_feature_snapshots
from app.services.mlb_client import MlbApiClient
from app.services.mlb_sync import sync_games_for_date

log = logging.getLogger(__name__)


async def _run() -> None:
    today = dt.datetime.now(dt.UTC).date()
    tomorrow = today + dt.timedelta(days=1)

    async with httpx.AsyncClient(timeout=60.0) as client:
        mlb = MlbApiClient(settings.mlb_api_base_url, client)

        async with async_session_factory() as session:
            for day in (today, tomorrow):
                await sync_games_for_date(session, mlb, day.isoformat(), fetch_details=True)
            await session.commit()
        log.info("games synced: %s + %s", today, tomorrow)

        async with async_session_factory() as session:
            mlb2 = MlbApiClient(settings.mlb_api_base_url, client)
            n = await rebuild_game_feature_snapshots(
                session,
                start_date=today,
                end_date=tomorrow,
                mlb=mlb2,
                low_memory=False,
            )
            await session.commit()

    log.info("done: snapshot rows written: %d (%s – %s)", n, today, tomorrow)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
