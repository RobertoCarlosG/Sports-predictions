from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

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


class MlbSyncRangeResponse(BaseModel):
    start_date: dt.date
    end_date: dt.date
    days_synced: int
