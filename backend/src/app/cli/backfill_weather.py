"""Rellena `game_weather` con el clima a la hora de inicio (Open-Meteo histórico + pronóstico).

Una petición por estadio, no por partido. Después hay que recalcular snapshots para que el
modelo vea el clima (``python -m app.cli.rebuild_feature_snapshots --season 2026``).

Uso (desde ``backend/``):

  python -m app.cli.backfill_weather --season 2026
  python -m app.cli.backfill_weather --start 2026-10-01 --end 2026-10-31 --only-missing
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging

import httpx
from sqlalchemy import func, select

from app.db.session import async_session_factory
from app.models.mlb import Game
from app.services.weather_open_meteo import backfill_weather_for_range

log = logging.getLogger(__name__)


async def _run(*, season: str | None, start: dt.date | None, end: dt.date | None, only_missing: bool) -> None:
    async with async_session_factory() as session:
        if start is None or end is None:
            stmt = select(func.min(Game.game_date), func.max(Game.game_date))
            if season is not None:
                stmt = stmt.where(Game.season == season)
            lo, hi = (await session.execute(stmt)).one()
            if lo is None:
                log.warning("no hay partidos para season=%s", season)
                return
            start, end = start or lo, end or hi
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await backfill_weather_for_range(
                session, start=start, end=end, client=client, season=season, only_missing=only_missing
            )
        await session.commit()
    log.info(
        "listo: %d partidos con clima, %d sin estadio en el JSON, %d sin datos",
        res.updated,
        res.unknown_venue,
        res.no_data,
    )


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Backfill de clima por partido (Open-Meteo).")
    p.add_argument("--season", default=None, help="Temporada, p. ej. 2026 (default: todas)")
    p.add_argument("--start", default=None, metavar="YYYY-MM-DD", help="Inicio (default: primer partido)")
    p.add_argument("--end", default=None, metavar="YYYY-MM-DD", help="Fin (default: último partido)")
    p.add_argument("--only-missing", action="store_true", help="Solo partidos sin fila en game_weather")
    args = p.parse_args(argv)
    asyncio.run(
        _run(
            season=args.season,
            start=dt.date.fromisoformat(args.start) if args.start else None,
            end=dt.date.fromisoformat(args.end) if args.end else None,
            only_missing=args.only_missing,
        )
    )


if __name__ == "__main__":
    main()
