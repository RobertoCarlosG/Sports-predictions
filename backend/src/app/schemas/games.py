from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    abbreviation: str


class GameSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game_pk: int
    season: str
    game_date: dt.date
    status: str
    home_team: TeamOut
    away_team: TeamOut


class GameDetailResponse(GameSummaryResponse):
    venue_id: int | None
    venue_name: str | None
    lineups: dict[str, Any] | None
    boxscore: dict[str, Any] | None
    weather: dict[str, Any] | None


class PredictionResponse(BaseModel):
    game_pk: int
    home_win_probability: float
    total_runs_estimate: float
    over_under_line: float
    model_version: str
