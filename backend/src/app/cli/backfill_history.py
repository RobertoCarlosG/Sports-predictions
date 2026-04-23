"""Descarga histórico MLB día a día (Fase 1 del pipeline).

Uso (desde el directorio `backend/`):

  uv run python -m app.cli.backfill_history --start 2025-03-20 --end 2025-04-20

Opcional: `--sleep 0.5` entre días para no presionar la API; `--no-fetch-details` más rápido pero sin boxscore/lineups.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import sys
import httpx

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.mlb_client import MlbApiClient
from app.services.mlb_sync import sync_games_for_date

log = logging.getLogger(__name__)


def _parse_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _daterange(start: dt.date, end: dt.date) -> list[dt.date]:
    if start > end:
        raise ValueError("start must be <= end")
    out: list[dt.date] = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += dt.timedelta(days=1)
    return out


async def _run_backfill(
    start: dt.date,
    end: dt.date,
    *,
    fetch_details: bool,
    sleep_s: float,
) -> None:
    dates = _daterange(start, end)
    async with httpx.AsyncClient(timeout=60.0) as client:
        mlb = MlbApiClient(settings.mlb_api_base_url, client)
        for i, d in enumerate(dates):
            async with async_session_factory() as session:
                try:
                    games = await sync_games_for_date(
                        session,
                        mlb,
                        d.isoformat(),
                        fetch_details=fetch_details,
                    )
                    await session.commit()
                    log.info(
                        "backfill %s (%d/%d): %d games",
                        d.isoformat(),
                        i + 1,
                        len(dates),
                        len(games),
                    )
                except Exception:
                    await session.rollback()
                    log.exception("backfill failed for %s", d.isoformat())
                    raise
            if sleep_s > 0 and i + 1 < len(dates):
                await asyncio.sleep(sleep_s)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Backfill MLB games into PostgreSQL by date range.")
    p.add_argument("--start", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument("--end", required=True, help="YYYY-MM-DD (inclusive)")
    p.add_argument(
        "--fetch-details",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fetch boxscore/linescore (default: true)",
    )
    p.add_argument(
        "--sleep",
        type=float,
        default=0.0,
        help="Seconds to wait between days (default: 0)",
    )
    args = p.parse_args(argv)
    start = _parse_date(args.start)
    end = _parse_date(args.end)
    asyncio.run(
        _run_backfill(
            start,
            end,
            fetch_details=args.fetch_details,
            sleep_s=args.sleep,
        )
    )


if __name__ == "__main__":
    main()
