"""Feature flags expuestos al frontend.

GET /api/v1/features — sin autenticación; solo lectura de settings.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class FeaturesResponse(BaseModel):
    nba_enabled: bool


@router.get("/features", response_model=FeaturesResponse)
async def get_features() -> FeaturesResponse:
    """Devuelve el estado de los feature flags del servidor."""
    return FeaturesResponse(nba_enabled=settings.nba_enabled)
