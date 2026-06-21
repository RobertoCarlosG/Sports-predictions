"""Recalcula `nba_game_feature_snapshots` desde `nba_games` (Fase 2 NBA).

Uso:

  # Toda la historia
  python -m app.cli.nba_rebuild_snapshots

  # Una temporada
  python -m app.cli.nba_rebuild_snapshots --season 2023-24 --window 10
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.db.session import async_session_factory
from app.services.nba_feature_snapshots import rebuild_nba_game_feature_snapshots

log = logging.getLogger(__name__)


async def _run(*, season: str | None, window: int) -> None:
    async with async_session_factory() as session:
        try:
            n = await rebuild_nba_game_feature_snapshots(
                session,
                rolling_window=window,
                season=season,
            )
            await session.commit()
            log.info("rebuilt %d NBA feature snapshot rows", n)
        except Exception:
            await session.rollback()
            raise


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Rebuild nba_game_feature_snapshots.")
    p.add_argument(
        "--season",
        default=None,
        help="Temporada a recalcular, p. ej. 2023-24. 'all' u omitir = todas.",
    )
    p.add_argument(
        "--window", type=int, default=10, help="Partidos rolling por equipo (default 10)"
    )
    args = p.parse_args(argv)
    season: str | None = None if args.season in (None, "all") else args.season
    asyncio.run(_run(season=season, window=args.window))


if __name__ == "__main__":
    main()
