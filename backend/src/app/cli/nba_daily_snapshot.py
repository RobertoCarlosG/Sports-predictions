"""ETL diario NBA: sincroniza hoy y mañana, evalúa aciertos y recalcula
``nba_game_feature_snapshots``.

Equivalente NBA del cron MLB (:mod:`app.cli.daily_snapshot`). Uso (desde `backend/`):

  uv run python -m app.cli.nba_daily_snapshot
"""

from __future__ import annotations

import asyncio
import logging
import os

# Rebuild largo: desactiva el statement_timeout por sentencia para esta sesión
# (el cap de 300s protege el API de queries desbocadas pero mataría el batch).
os.environ.setdefault("DATABASE_STATEMENT_TIMEOUT_SECONDS", "0")

from app.services.nba_daily_snapshot import run_nba_daily_snapshot

log = logging.getLogger(__name__)


async def _run() -> None:
    result = await run_nba_daily_snapshot()
    log.info(
        "done: synced %s + %s (%d games) | snapshot rows written: %d",
        result.today_utc,
        result.tomorrow_utc,
        result.games_synced,
        result.snapshot_rows,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
