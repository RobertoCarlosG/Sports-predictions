from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.ml.predictor import MlbPredictionService
from app.models.mlb import Game
from app.schemas.games import PredictionResponse

router = APIRouter()


@router.get("/predict/{game_pk}", response_model=PredictionResponse)
async def predict_game(
    game_pk: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PredictionResponse:
    svc: MlbPredictionService = request.app.state.prediction_service
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == game_pk)
        .options(selectinload(Game.weather))
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    pr = svc.predict(game, game.weather)
    return PredictionResponse(
        game_pk=pr.game_pk,
        home_win_probability=pr.home_win_probability,
        total_runs_estimate=pr.total_runs_estimate,
        over_under_line=pr.over_under_line,
        model_version=pr.model_version,
    )
