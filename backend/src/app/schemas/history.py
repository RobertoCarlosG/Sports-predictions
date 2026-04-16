from __future__ import annotations

import datetime as dt
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.games import TeamOut


class HistoryGameOut(BaseModel):
    """Resultado histórico genérico; `sport_code` distingue MLB / NBA / etc."""

    sport_code: str = Field(default="mlb", description="Identificador del deporte o liga")
    game_pk: int
    season: str
    game_date: dt.date
    status: str
    home_team: TeamOut
    away_team: TeamOut
    home_score: int | None = None
    away_score: int | None = None
    winner_team_id: int | None = None


class MlbSyncRangeBody(BaseModel):
    start_date: dt.date
    end_date: dt.date
    fetch_details: bool = Field(
        default=False,
        description="Si true, descarga boxscore y live feed por día (más lento).",
    )

    @model_validator(mode="after")
    def _sync_range_current_year_only(self) -> Self:
        today = dt.date.today()
        y = today.year
        if self.start_date.year != y or self.end_date.year != y:
            raise ValueError("Las fechas deben estar en el año civil en curso.")
        if self.start_date < dt.date(y, 1, 1) or self.end_date > dt.date(y, 12, 31):
            raise ValueError("Rango inválido para el año en curso.")
        if self.end_date < self.start_date:
            raise ValueError("La fecha fin debe ser >= la fecha inicio.")
        if self.start_date > today or self.end_date > today:
            raise ValueError("No se permiten fechas futuras.")
        return self


class MlbSyncRangeResponse(BaseModel):
    start_date: dt.date
    end_date: dt.date
    days_synced: int


class MlbSyncGameBody(BaseModel):
    fetch_details: bool = Field(
        default=True,
        description="Si true, descarga boxscore y live feed (más lento).",
    )
