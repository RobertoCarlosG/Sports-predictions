"""Atajo para predicciones atascadas en ~50%: recalcula indicadores de la temporada
actual y vacía la caché de estimaciones.

Equivalente al botón "Arreglar predicciones al 50%" del panel admin o a:
  POST /api/v1/admin/pipeline/fix-fifty

Nota: el reload del modelo en memoria del servidor (Render) NO se puede hacer desde
este CLI — es estado del proceso remoto. Como el predictor detecta cambios de archivo
automáticamente en cada request, el servidor recoge el modelo nuevo sin necesidad de
un reload explícito tras re-entrenar.

Si tras esto un partido sigue en ~50%, falta histórico previo:
ver docs/ml_fix_fifty_runbook.md (Caso B).

Uso (desde `backend/`):

  uv run python -m app.cli.fix_fifty
  uv run python -m app.cli.fix_fifty --season 2026   # temporada explícita
  uv run python -m app.cli.fix_fifty --window 15      # ventana rolling personalizada
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging

import httpx

from app.db.session import async_session_factory
from app.services.feature_snapshots import rebuild_game_feature_snapshots
from app.services.mlb_client import MlbApiClient
from app.services.prediction_cache import clear_prediction_cache
from app.core.config import settings

log = logging.getLogger(__name__)


async def _run(*, season: str, window: int) -> None:
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        mlb = MlbApiClient(settings.mlb_api_base_url, http_client)
        async with async_session_factory() as session:
            try:
                n_snap = await rebuild_game_feature_snapshots(
                    session, rolling_window=window, season=season, mlb=mlb
                )
                n_cache = await clear_prediction_cache(session)
                await session.commit()
                log.info(
                    "fix-fifty done: %d snapshot rows rebuilt, %d cache rows cleared (season=%s)",
                    n_snap,
                    n_cache,
                    season,
                )
                log.info(
                    "El servidor (Render) recargará el modelo automáticamente en el próximo request."
                )
            except Exception:
                await session.rollback()
                raise


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Fix ~50% predictions: rebuild snapshots + clear cache.")
    p.add_argument(
        "--season",
        default=None,
        help="Season to rebuild (default: current calendar year)",
    )
    p.add_argument("--window", type=int, default=10, help="Rolling games per team (default 10)")
    args = p.parse_args(argv)
    season = args.season or str(dt.date.today().year)
    asyncio.run(_run(season=season, window=args.window))


if __name__ == "__main__":
    main()
