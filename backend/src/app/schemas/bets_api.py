"""Schemas API control de apuestas."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BetBankCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    initial_amount: float = Field(gt=0)
    currency: str = Field(default="USD", max_length=8)


class BetBankUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool | None = None


class BetBankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    initial_amount: float
    currency: str
    is_active: bool
    created_at: dt.datetime


class BetPeriodCreate(BaseModel):
    bank_id: int
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class BetPeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bank_id: int
    name: str
    year: int
    month: int
    starting_balance: float
    closing_balance: float | None
    status: str
    closed_at: dt.datetime | None
    created_at: dt.datetime


class BetPeriodStatsOut(BaseModel):
    period_id: int
    name: str
    starting_balance: float
    closing_balance: float | None
    status: str
    total_stake: float
    realized_pnl: float
    roi_pct: float | None
    decided_bets: int
    wins: int
    losses: int
    pushes: int
    pending: int
    win_rate_ml_pct: float | None
    win_rate_ou_pct: float | None


class BetCreate(BaseModel):
    bank_id: int
    game_pk: int
    bet_type: Literal["moneyline", "over_under"]
    bet_side: Literal["home", "away", "over", "under"]
    stake: float = Field(gt=0)
    odds: float = Field(ge=1.0)
    ou_line: float | None = None
    notes: str | None = None


class BetUpdate(BaseModel):
    notes: str | None = None
    status: Literal["cancelled"] | None = None


class BetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    bank_id: int
    period_id: int
    game_pk: int
    bet_type: str
    bet_side: str
    stake: float
    odds: float
    ou_line: float | None
    status: str
    result_source: str | None
    result_checked_at: dt.datetime | None
    notes: str | None
    created_at: dt.datetime
    realized_profit: float | None = None


class BetsStatsOut(BaseModel):
    total_stake: float
    realized_pnl: float
    roi_pct: float | None
    decided_bets: int
    wins: int
    losses: int
    pushes: int
    pending: int
    by_type: dict[str, dict[str, float | int | None]]
