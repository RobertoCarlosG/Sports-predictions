"""Endpoint público de información del modelo activo.

Solo expone metadata mínima (versión, base, fecha de carga, flag sintético) para
que la app pública pueda mostrar qué modelo está sirviendo predicciones sin
revelar métricas detalladas a usuarios anónimos. El histórico y las métricas
completas viven en `/admin/model/...`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.admin_api import PublicModelInfoResponse
from app.services.model_registry import get_active_model_version

router = APIRouter()


@router.get("/model/info", response_model=PublicModelInfoResponse)
async def public_model_info(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PublicModelInfoResponse:
    row = await get_active_model_version(session)
    if row is None:
        return PublicModelInfoResponse(model_loaded=False)
    return PublicModelInfoResponse(
        model_loaded=True,
        model_version=row.model_version,
        base_version=row.base_version,
        is_synthetic=row.is_synthetic,
        loaded_at=row.loaded_at.isoformat(),
    )
