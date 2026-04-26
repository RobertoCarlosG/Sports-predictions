from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

PredictedWinnerSide = Literal["home", "away"]
ActualWinnerSide = Literal["home", "away", "tie"]
OUSide = Literal["over", "under"]
OUUserOutcome = Literal["win", "loss", "push"]


class BacktestSummary(BaseModel):
    n_games: int = Field(description="Partidos en el universo filtrado (con ambos mercados o ML evaluado)")

    ml_wins: int
    ml_losses: int

    ou_wins: int
    ou_losses: int
    ou_pushes: int

    global_hit_rate_pct: float | None = Field(
        default=None,
        description=(
            "(aciertos_ML + aciertos_OU) / (2·n − pushes_OU) × 100. "
            "Los pushes de O/U no suman al denominador."
        ),
    )
    total_decided_picks: int = Field(
        description="2·n − ou_picks excl. push (cada juego: 1 pick ML + 0 o 1 pick O/U si no hubo push)"
    )
    total_correct_picks: int = Field(
        description="Aciertos ML + aciertos O/U (pushes de O/U no suman al numerador)"
    )


class BacktestTimePoint(BaseModel):
    game_date: dt.date
    games_count: int
    ml_hit_rate_pct: float | None = Field(default=None, description="Nulo si games_count=0")
    ou_hit_rate_pct: float | None = Field(
        default=None, description="Nulo si no hay picks O/U decididos (todos push o 0 juegos)"
    )
    ou_decided: int = Field(description="Juegos de ese día con O/U contado (no push)")


class BacktestGameRow(BaseModel):
    game_pk: int
    game_date: dt.date
    game_datetime_utc: dt.datetime | None = None
    away_abbr: str
    home_abbr: str
    matchup_label: str

    p_home: float
    ml_confidence: float = Field(description="max(p_home, 1−p_home) del lado predicho")
    predicted_winner: PredictedWinnerSide
    actual_winner: ActualWinnerSide
    ml_correct: bool

    over_under_line: float
    total_runs_estimate: float
    predicted_ou: OUSide
    total_runs_actual: int
    ou_outcome: OUUserOutcome
    ou_correct: bool | None = Field(
        default=None, description="Nulo en push; True/False en over/under decidido"
    )

    success_count: int = Field(
        description="0–2: aciertos de mercado (ML + O/U; push O/U no suma 1 de 2 de forma de acierto)"
    )
    success_label: str = Field(
        description='Texto p. ej. "2/2 Aciertos", "1/2", "0/2", "1/1" si push en O/U'
    )


class BacktestResponse(BaseModel):
    date_from: dt.date
    date_to: dt.date
    min_confidence: float
    skip_empty_days: bool
    summary: BacktestSummary
    timeseries: list[BacktestTimePoint]
    games: list[BacktestGameRow]
