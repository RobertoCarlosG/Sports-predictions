from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_rate_limit import rate_limit_public_read, rate_limit_public_write
from app.db.session import get_db
from app.ml.predictor import MlbPredictionService
from app.services.prediction_cache import get_cached_prediction, upsert_prediction_cache
from app.services.prediction_infer import compute_prediction_response
from app.schemas.games import PredictionResponse

router = APIRouter()
log = logging.getLogger(__name__)


def _get_prediction_service(request: Request) -> MlbPredictionService:
    svc: MlbPredictionService | None = getattr(request.app.state, "prediction_service", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Modelo no disponible. Entrena el modelo, configura ML_MODEL_PATH y usa "
                "administración para recargar, o reinicia el servicio."
            ),
        )
    return svc


@router.get(
    "/predict/{game_pk}",
    response_model=PredictionResponse,
    dependencies=[Depends(rate_limit_public_read)],
)
async def predict_game(
    game_pk: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PredictionResponse:
    """Sirve estimación desde caché si coincide la versión del modelo; si no, calcula y guarda."""
    svc = _get_prediction_service(request)
    model_version = svc.model_version
    request.app.state.active_model_version = model_version
    if model_version:
        cached = await get_cached_prediction(session, game_pk, model_version)
        if cached is not None:
            return cached

    try:
        out = await compute_prediction_response(session, svc, game_pk)
    except HTTPException:
        raise
    except Exception:
        log.exception("predict failed game_pk=%s", game_pk)
        raise HTTPException(status_code=500, detail="Error al calcular la estimación.") from None

    try:
        await upsert_prediction_cache(session, out, "api_get")
    except Exception:
        log.warning("prediction cache upsert failed game_pk=%s", game_pk, exc_info=True)
    return out


@router.post(
    "/predict/{game_pk}/refresh",
    response_model=PredictionResponse,
    dependencies=[Depends(rate_limit_public_write)],
)
async def refresh_prediction_game(
    game_pk: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PredictionResponse:
    """Recalcula y actualiza la caché."""
    svc = _get_prediction_service(request)
    try:
        out = await compute_prediction_response(session, svc, game_pk)
    except HTTPException:
        raise
    except Exception:
        log.exception("predict refresh failed game_pk=%s", game_pk)
        raise HTTPException(status_code=500, detail="Error al calcular la estimación.") from None

    try:
        await upsert_prediction_cache(session, out, "api_refresh")
    except Exception:
        log.warning("prediction cache upsert failed game_pk=%s", game_pk, exc_info=True)
    return out
