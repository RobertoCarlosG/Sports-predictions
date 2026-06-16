"""ETL diario: sincroniza hoy y mañana desde MLB API y recalcula game_feature_snapshots.

Equivalente al botón "ETL diario" del panel admin o a:
  POST /api/v1/admin/pipeline/mlb-daily-snapshot

Uso (desde `backend/`):

  uv run python -m app.cli.daily_snapshot
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.services.mlb_daily_snapshot import run_mlb_daily_snapshot

log = logging.getLogger(__name__)


async def _run() -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        result = await run_mlb_daily_snapshot(client)
    log.info(
        "done: synced %s + %s | snapshot rows written: %d (season %s)",
        result.today_utc,
        result.tomorrow_utc,
        result.snapshot_rows,
        result.season,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
