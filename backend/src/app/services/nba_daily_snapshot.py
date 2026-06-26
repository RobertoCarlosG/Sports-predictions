"""Sincronización diaria del calendario NBA (hoy + mañana) + evaluación de
aciertos de partidos finalizados + rebuild de ``nba_game_feature_snapshots``.

Espeja :mod:`app.services.mlb_daily_snapshot`. Diferencias frente a MLB:

* ``NbaApiClient`` es autónomo (no recibe un ``httpx.AsyncClient``).
* El rebuild NBA no hace red: lee ``boxscore_json`` ya guardado en la BD, así
  que no necesita cliente de API.
* Se reconstruyen **todos** los snapshots (``season=None``) porque las cadenas de
  temporada en BD no son homogéneas (``leaguegamelog`` escribe ``SEASON_ID``
  tipo ``"22023"``; ``scoreboard`` escribe ``SEASON`` tipo ``"2024"``). Pasar
  ``season`` filtraría y los partidos de hoy/mañana podrían quedarse sin fila.

Habilitar con ``NBA_DAILY_SNAPSHOT_ENABLED=true``. Hora UTC configurable.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from dataclasses import dataclass

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.nba_client import NbaApiClient
from app.services.nba_feature_snapshots import rebuild_nba_game_feature_snapshots
from app.services.nba_prediction_cache import evaluate_nba_predictions_for_final_games
from app.services.nba_sync import sync_games_for_date

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class NbaDailySnapshotResult:
    today_utc: str
    tomorrow_utc: str
    games_synced: int
    snapshot_rows: int


def _seconds_until_next_utc_run(hour: int, minute: int) -> float:
    now = dt.datetime.now(dt.UTC)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += dt.timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def run_nba_daily_snapshot(*, client: NbaApiClient | None = None) -> NbaDailySnapshotResult:
    """Importa los partidos NBA de hoy y mañana (UTC), evalúa los aciertos de los
    ya finalizados y recalcula ``nba_game_feature_snapshots``.

    Reutilizable desde el crono (:func:`nba_daily_snapshot_loop_forever`) y desde
    un endpoint admin bajo demanda.
    """
    nba = client or NbaApiClient()
    today = dt.datetime.now(dt.UTC).date()
    tomorrow = today + dt.timedelta(days=1)

    async with async_session_factory() as session:
        synced = []
        for offset in (0, 1):
            day = today + dt.timedelta(days=offset)
            synced.extend(await sync_games_for_date(session, nba, day.isoformat()))
        # G4: marca aciertos de los partidos finalizados que ya tengan predicción cacheada.
        await evaluate_nba_predictions_for_final_games(session, synced)
        await session.commit()
        games_synced = len(synced)

    async with async_session_factory() as session:
        # season=None → reconstruye todos los snapshots (ver nota de cabecera).
        snapshot_rows = await rebuild_nba_game_feature_snapshots(session, season=None)
        await session.commit()

    log.info(
        "NBA daily snapshot: synced %s + %s (%d games), rebuild wrote %d snapshot rows",
        today.isoformat(),
        tomorrow.isoformat(),
        games_synced,
        snapshot_rows,
    )
    return NbaDailySnapshotResult(
        today_utc=today.isoformat(),
        tomorrow_utc=tomorrow.isoformat(),
        games_synced=games_synced,
        snapshot_rows=snapshot_rows,
    )


async def run_nba_daily_snapshot_job() -> None:
    """Misma lógica que :func:`run_nba_daily_snapshot` para tareas en segundo
    plano (solo efectos, sin retorno)."""
    await run_nba_daily_snapshot()


async def nba_daily_snapshot_loop_forever() -> None:
    while True:
        delay = _seconds_until_next_utc_run(
            settings.nba_daily_snapshot_utc_hour,
            settings.nba_daily_snapshot_utc_minute,
        )
        log.info(
            "NBA daily snapshot: siguiente ejecución en %.0fs (UTC %02d:%02d)",
            delay,
            settings.nba_daily_snapshot_utc_hour,
            settings.nba_daily_snapshot_utc_minute,
        )
        await asyncio.sleep(delay)
        try:
            await run_nba_daily_snapshot_job()
        except Exception:
            log.exception("NBA daily snapshot job failed")
