"""Recalcula `game_feature_snapshots` desde `games` + `game_weather` (Fase 2).

Uso:

  uv run python -m app.cli.rebuild_feature_snapshots
  uv run python -m app.cli.rebuild_feature_snapshots --season 2025 --window 10
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.feature_snapshots import rebuild_game_feature_snapshots
from app.services.mlb_client import MlbApiClient

log = logging.getLogger(__name__)


async def _run(*, season: str | None, window: int) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        mlb = MlbApiClient(settings.mlb_api_base_url, client)
        async with async_session_factory() as session:
            try:
                n = await rebuild_game_feature_snapshots(
                    session, rolling_window=window, season=season, mlb=mlb
                )
                await session.commit()
                log.info("rebuilt %d feature snapshot rows", n)
            except Exception:
                await session.rollback()
                raise


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Rebuild game_feature_snapshots from games table.")
    p.add_argument("--season", default=None, help="Filter by season string e.g. 2025")
    p.add_argument("--window", type=int, default=10, help="Rolling games per team (default 10)")
    args = p.parse_args(argv)
    asyncio.run(_run(season=args.season, window=args.window))


if __name__ == "__main__":
    main()
