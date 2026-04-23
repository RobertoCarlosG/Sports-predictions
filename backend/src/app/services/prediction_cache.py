from __future__ import annotations

import datetime as dt

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mlb import GamePredictionCache
from app.schemas.games import PredictionResponse


async def get_cached_prediction(
    session: AsyncSession,
    game_pk: int,
    model_version: str,
) -> PredictionResponse | None:
    row = await session.get(GamePredictionCache, game_pk)
    if row is None or row.model_version != model_version:
        return None
    return PredictionResponse(
        game_pk=row.game_pk,
        home_win_probability=row.home_win_probability,
        total_runs_estimate=row.total_runs_estimate,
        over_under_line=row.over_under_line,
        model_version=row.model_version,
    )


async def upsert_prediction_cache(
    session: AsyncSession,
    response: PredictionResponse,
    trigger_reason: str | None,
) -> None:
    now = dt.datetime.now(dt.UTC)
    row = await session.get(GamePredictionCache, response.game_pk)
    if row is None:
        row = GamePredictionCache(
            game_pk=response.game_pk,
            home_win_probability=response.home_win_probability,
            total_runs_estimate=response.total_runs_estimate,
            over_under_line=response.over_under_line,
            model_version=response.model_version,
            trigger_reason=trigger_reason,
            computed_at=now,
        )
        session.add(row)
    else:
        row.home_win_probability = response.home_win_probability
        row.total_runs_estimate = response.total_runs_estimate
        row.over_under_line = response.over_under_line
        row.model_version = response.model_version
        row.trigger_reason = trigger_reason
        row.computed_at = now


async def clear_prediction_cache(session: AsyncSession) -> int:
    res = await session.execute(delete(GamePredictionCache))
    return res.rowcount or 0
