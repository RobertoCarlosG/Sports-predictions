from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ml.predictor import MlbPredictionService, PredictionResult
from app.models.mlb import Game, GameFeatureSnapshot
from app.schemas.games import PredictionResponse
from app.services.prediction_cache import ml_pick_from_home_win_probability


def prediction_response_from_result(pr: PredictionResult) -> PredictionResponse:
    """Alineado con ``upsert_prediction_cache``: pick explícito para API y front."""
    predicted_winner = ml_pick_from_home_win_probability(pr.home_win_probability)
    return PredictionResponse(
        game_pk=pr.game_pk,
        home_win_probability=pr.home_win_probability,
        total_runs_estimate=pr.total_runs_estimate,
        over_under_line=pr.over_under_line,
        model_version=pr.model_version,
        predicted_winner=predicted_winner,
    )


async def compute_prediction_response(
    session: AsyncSession,
    svc: MlbPredictionService,
    game_pk: int,
) -> PredictionResponse:
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == game_pk)
        .options(selectinload(Game.weather))
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    snap_row = await session.execute(
        select(GameFeatureSnapshot).where(GameFeatureSnapshot.game_pk == game_pk)
    )
    snapshot = snap_row.scalar_one_or_none()
    pr = svc.predict(game, game.weather, snapshot)
    return prediction_response_from_result(pr)
