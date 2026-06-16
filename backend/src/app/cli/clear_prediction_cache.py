"""Vacía la tabla `prediction_results` (caché de estimaciones).

Equivalente al botón "Limpiar caché" del panel admin o a:
  POST /api/v1/admin/pipeline/clear-prediction-cache

Útil después de recalcular snapshots o reentrenar el modelo, para que las
predicciones se recalculen con los datos/modelo nuevos en el próximo request.

Uso (desde `backend/`):

  uv run python -m app.cli.clear_prediction_cache
"""

from __future__ import annotations

import asyncio
import logging

from app.db.session import async_session_factory
from app.services.prediction_cache import clear_prediction_cache

log = logging.getLogger(__name__)


async def _run() -> None:
    async with async_session_factory() as session:
        try:
            n = await clear_prediction_cache(session)
            await session.commit()
            log.info("deleted %d rows from prediction_results", n)
        except Exception:
            await session.rollback()
            raise


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
