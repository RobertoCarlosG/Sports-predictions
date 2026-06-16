"""Recalcula `game_feature_snapshots` desde `games` + `game_weather` (Fase 2).

Uso:

  # Toda la historia
  python -m app.cli.rebuild_feature_snapshots

  # Una temporada
  python -m app.cli.rebuild_feature_snapshots --season 2026 --window 10

  # Rango de fechas específico (escenarios 2 y 3)
  python -m app.cli.rebuild_feature_snapshots --start 2026-06-01 --end 2026-06-14

  # Últimos 7 días
  python -m app.cli.rebuild_feature_snapshots --last-days 7
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging

import httpx

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.feature_snapshots import rebuild_game_feature_snapshots
from app.services.mlb_client import MlbApiClient

log = logging.getLogger(__name__)


async def _run(
    *,
    season: str | None,
    window: int,
    start_date: dt.date | None,
    end_date: dt.date | None,
) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        mlb = MlbApiClient(settings.mlb_api_base_url, client)
        async with async_session_factory() as session:
            try:
                n = await rebuild_game_feature_snapshots(
                    session,
                    rolling_window=window,
                    season=season,
                    mlb=mlb,
                    start_date=start_date,
                    end_date=end_date,
                )
                await session.commit()
                log.info("rebuilt %d feature snapshot rows", n)
            except Exception:
                await session.rollback()
                raise


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description="Rebuild game_feature_snapshots from games table.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--season",
        default=None,
        help="Season to rebuild e.g. 2026. 'all' or omit = every season. Ignored when --start/--end are set.",
    )
    p.add_argument("--window", type=int, default=10, help="Rolling games per team (default 10)")
    p.add_argument("--start", default=None, metavar="YYYY-MM-DD", help="Start date (inclusive). Requires --end.")
    p.add_argument("--end", default=None, metavar="YYYY-MM-DD", help="End date (inclusive). Requires --start.")
    p.add_argument(
        "--last-days",
        type=int,
        default=None,
        metavar="N",
        help="Shortcut: rebuild the last N days up to today. Overrides --start/--end/--season.",
    )
    args = p.parse_args(argv)

    start_date: dt.date | None = None
    end_date: dt.date | None = None
    season: str | None = None if args.season in (None, "all") else args.season

    if args.last_days is not None:
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=args.last_days - 1)
        log.info("--last-days %d → range %s to %s", args.last_days, start_date, end_date)
    elif args.start or args.end:
        if not (args.start and args.end):
            p.error("--start and --end must be used together")
        start_date = dt.date.fromisoformat(args.start)
        end_date = dt.date.fromisoformat(args.end)
        if start_date > end_date:
            p.error("--start must be <= --end")

    asyncio.run(_run(season=season, window=args.window, start_date=start_date, end_date=end_date))


if __name__ == "__main__":
    main()
