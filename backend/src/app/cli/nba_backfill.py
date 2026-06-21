"""Backfill de partidos NBA por temporada vía leaguegamelog (Fase 1 NBA).

Uso:

  # Una temporada
  python -m app.cli.nba_backfill --season 2023-24

  # Varias temporadas
  python -m app.cli.nba_backfill --season 2021-22 --season 2022-23 --season 2023-24
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from app.db.session import async_session_factory
from app.services.nba_client import NbaApiClient, parse_league_game_log
from app.services.nba_sync import upsert_parsed_games

log = logging.getLogger(__name__)


async def _run(seasons: list[str], season_type: str) -> None:
    client = NbaApiClient(season_type=season_type)
    for season in seasons:
        # 1. Fetch desde la API FUERA de la sesión DB para no mantener
        #    una conexión abierta mientras esperamos la red (stats.nba.com
        #    puede tardar 20-40 s y disparar el statement_timeout del servidor).
        log.info("season %s: fetching from nba_api …", season)
        rows = await client.league_game_log(season, season_type=season_type)
        parsed = parse_league_game_log(rows)
        log.info("season %s: %d game records received, writing to DB …", season, len(parsed))

        # 2. Abrir sesión solo para los INSERTs (operación rápida).
        async with async_session_factory() as session:
            try:
                games = await upsert_parsed_games(session, parsed, season)
                await session.commit()
                log.info("season %s: %d games upserted", season, len(games))
            except Exception:
                await session.rollback()
                raise


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Backfill de partidos NBA por temporada.")
    p.add_argument(
        "--season",
        action="append",
        required=True,
        help="Temporada formato '2023-24'. Repetible para varias temporadas.",
    )
    p.add_argument(
        "--season-type",
        default="Regular Season",
        help="Tipo de temporada (default: 'Regular Season').",
    )
    args = p.parse_args(argv)
    asyncio.run(_run(args.season, args.season_type))


if __name__ == "__main__":
    main()
