"""Schemas de respuesta NBA (espeja schemas/games.py, semántica de basket)."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict


class NbaTeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    abbreviation: str
    conference: str | None = None
    division: str | None = None


class NbaPredictionResponse(BaseModel):
    game_id: str
    home_win_probability: float
    margin_estimate: float
    total_points_estimate: float
    spread_line: float
    over_under_line: float
    over_probability: float | None = None
    model_version: str
    defaults_injected: bool = False
    predicted_winner: str | None = None
    actual_winner: str | None = None
    is_correct: bool | None = None
    evaluated_at: str | None = None


class NbaGameDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game_id: str
    season: str
    game_date: dt.date
    status: str
    home_team: NbaTeamOut
    away_team: NbaTeamOut
    home_score: int | None = None
    away_score: int | None = None
    arena: str | None = None
    boxscore: dict[str, Any] | None = None
    prediction: NbaPredictionResponse | None = None


class NbaGamesListMeta(BaseModel):
    warnings: list[str] = []
    info: list[str] = []
    missing_snapshot_count: int = 0


class NbaGamesListResponse(BaseModel):
    games: list[NbaGameDetailResponse]
    meta: NbaGamesListMeta
