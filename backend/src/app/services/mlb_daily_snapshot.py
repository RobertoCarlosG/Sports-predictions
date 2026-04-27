"""Sincronización diaria del calendario MLB (hoy + mañana) + rebuild de game_feature_snapshots.

Habilitar con MLB_DAILY_SNAPSHOT_ENABLED=true (p. ej. en Render). Hora UTC configurable.
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


def _seconds_until_next_utc_run(hour: int, minute: int) -> float:
    now = dt.datetime.now(dt.UTC)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def run_mlb_daily_snapshot_job(http_client: httpx.AsyncClient) -> None:
    """
    Importa partidos para hoy y mañana (fecha UTC) y recalcula snapshots de la temporada actual.
    """
    today = dt.datetime.now(dt.UTC).date()
    season = str(today.year)
    async with async_session_factory() as session:
        mlb = MlbApiClient(settings.mlb_api_base_url, http_client)
        for offset in (0, 1):
            day = today + dt.timedelta(days=offset)
            await sync_games_for_date(session, mlb, day.isoformat(), fetch_details=True)
        await session.commit()

    async with async_session_factory() as session:
        mlb = MlbApiClient(settings.mlb_api_base_url, http_client)
        n = await rebuild_game_feature_snapshots(session, season=season, mlb=mlb)
        await session.commit()
    log.info(
        "MLB daily snapshot: synced %s + %s, rebuild wrote %s snapshot rows (season=%s)",
        today.isoformat(),
        (today + dt.timedelta(days=1)).isoformat(),
        n,
        season,
    )


async def daily_snapshot_loop_forever(http_client: httpx.AsyncClient) -> None:
    while True:
        delay = _seconds_until_next_utc_run(
            settings.mlb_daily_snapshot_utc_hour,
            settings.mlb_daily_snapshot_utc_minute,
        )
        log.info(
            "MLB daily snapshot: siguiente ejecución en %.0fs (UTC %02d:%02d)",
            delay,
            settings.mlb_daily_snapshot_utc_hour,
            settings.mlb_daily_snapshot_utc_minute,
        )
        await asyncio.sleep(delay)
        try:
            await run_mlb_daily_snapshot_job(http_client)
        except Exception:
            log.exception("MLB daily snapshot job failed")
