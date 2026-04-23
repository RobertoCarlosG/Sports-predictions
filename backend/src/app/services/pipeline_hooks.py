from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.prediction_cache import upsert_prediction_cache
from app.services.prediction_infer import compute_prediction_response

if TYPE_CHECKING:
    from app.ml.predictor import MlbPredictionService

log = logging.getLogger(__name__)


async def refresh_prediction_cache_for_games(
    app: FastAPI,
    game_pks: list[int],
    trigger_reason: str,
) -> None:
    """Precalcula y guarda estimaciones (solo si el modelo está cargado y el flag auto está activo)."""
    if not settings.pipeline_auto_cache_predictions:
        return
    await asyncio.sleep(0.08)
    svc: MlbPredictionService | None = getattr(app.state, "prediction_service", None)
    model_version: str = getattr(app.state, "active_model_version", "") or ""
    if svc is None or not model_version:
        log.debug("skip auto prediction cache: no model loaded")
        return
    unique = sorted(set(game_pks))
    if not unique:
        return
    async with async_session_factory() as session:
        for pk in unique:
            try:
                resp = await compute_prediction_response(session, svc, pk)
            except Exception:
                log.warning("auto cache skip game_pk=%s", pk, exc_info=False)
                continue
            await upsert_prediction_cache(session, resp, trigger_reason)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            log.exception("auto prediction cache commit failed")
