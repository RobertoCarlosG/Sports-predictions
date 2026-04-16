from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession


class SportHistoryAdapter(Protocol):
    """Plantilla para consultas históricas: cada deporte aporta su implementación.

    Los campos de resultado (goles, runs, puntos) y los filtros útiles no son
    comunes a todos los deportes; el código de ruta por deporte decide el
    mapeo a DTOs compartidos (`HistoryGameOut` con `sport_code`).
    """

    sport_code: str

    async def list_games(
        self,
        session: AsyncSession,
        *,
        season: str | None,
        team_id: int | None,
        date_from: Any,
        date_to: Any,
        only_final: bool,
        only_with_scores: bool,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Devuelve dicts compatibles con `HistoryGameOut`."""
        ...
