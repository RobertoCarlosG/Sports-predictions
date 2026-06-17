from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_rate_limit import rate_limit_public_read, rate_limit_public_write
from app.db.session import get_db
from app.ml.model_routing import (
    DEFAULT_ML_MODEL,
    get_prediction_service,
    sync_primary_model_version,
)
from app.schemas.games import PredictionResponse
from app.services.prediction_cache import get_cached_prediction, upsert_prediction_cache
from app.services.prediction_infer import (
    attach_asian_handicap_if_missing,
    compute_prediction_response,
)

router = APIRouter()
log = logging.getLogger(__name__)


@router.get(
    "/predict/{game_pk}",
    response_model=PredictionResponse,
    dependencies=[Depends(rate_limit_public_read)],
)
async def predict_game(
    game_pk: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    model: Literal["rf", "xgb"] = Query(
        default=DEFAULT_ML_MODEL,
        description="Model to use: 'xgb' (XGBoost, default) or 'rf' (Random Forest)",
    ),
) -> PredictionResponse:
    """Sirve estimación desde caché si coincide la versión del modelo; si no, calcula y guarda."""
    svc = get_prediction_service(request, model)
    model_version = svc.model_version
    sync_primary_model_version(request, model, svc)
    if model_version:
        cached = await get_cached_prediction(session, game_pk, model_version)
        if cached is not None:
            return await attach_asian_handicap_if_missing(session, cached)

    try:
        out = await compute_prediction_response(session, svc, game_pk)
    except HTTPException:
        raise
    except Exception:
        log.exception("predict failed game_pk=%s model=%s", game_pk, model)
        raise HTTPException(status_code=500, detail="Error al calcular la estimación.") from None

    try:
        await upsert_prediction_cache(session, out, f"api_get_{model}")
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
    model: Literal["rf", "xgb"] = Query(
        default=DEFAULT_ML_MODEL,
        description="Model to use: 'xgb' (default) or 'rf'",
    ),
) -> PredictionResponse:
    """Recalcula y actualiza la caché."""
    svc = get_prediction_service(request, model)
    sync_primary_model_version(request, model, svc)
    try:
        out = await compute_prediction_response(session, svc, game_pk)
    except HTTPException:
        raise
    except Exception:
        log.exception("predict refresh failed game_pk=%s model=%s", game_pk, model)
        raise HTTPException(status_code=500, detail="Error al calcular la estimación.") from None

    try:
        await upsert_prediction_cache(session, out, f"api_refresh_{model}")
    except Exception:
        log.warning("prediction cache upsert failed game_pk=%s", game_pk, exc_info=True)
    return out
