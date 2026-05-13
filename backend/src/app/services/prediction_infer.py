from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ml.predictor import MlbPredictionService, PredictionResult, compute_asian_handicap
from app.models.mlb import Game, GameFeatureSnapshot
from app.schemas.games import AsianHandicapBlock, AsianHandicapSideOut, PredictionResponse
from app.services.prediction_cache import ml_pick_from_home_win_probability


def prediction_response_from_result(
    pr: PredictionResult,
    *,
    home_abbr: str,
    away_abbr: str,
) -> PredictionResponse:
    """Alineado con ``upsert_prediction_cache``: pick explícito para API y front."""
    predicted_winner = ml_pick_from_home_win_probability(pr.home_win_probability)
    ah_raw = compute_asian_handicap(
        pr.home_win_probability,
        pr.total_runs_estimate,
        home_abbr,
        away_abbr,
    )
    asian = AsianHandicapBlock(
        home=AsianHandicapSideOut.model_validate(ah_raw["home"]),
        away=AsianHandicapSideOut.model_validate(ah_raw["away"]),
    )
    return PredictionResponse(
        game_pk=pr.game_pk,
        home_win_probability=pr.home_win_probability,
        total_runs_estimate=pr.total_runs_estimate,
        over_under_line=pr.over_under_line,
        model_version=pr.model_version,
        predicted_winner=predicted_winner,
        asian_handicap=asian,
    )


async def attach_asian_handicap_if_missing(session: AsyncSession, out: PredictionResponse) -> PredictionResponse:
    """Añade handicap asiático cuando la respuesta viene de caché sin equipos."""
    if out.asian_handicap is not None:
        return out
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == out.game_pk)
        .options(selectinload(Game.home_team), selectinload(Game.away_team)),
    )
    game = result.scalar_one_or_none()
    if game is None or game.home_team is None or game.away_team is None:
        return out
    ah_raw = compute_asian_handicap(
        out.home_win_probability,
        out.total_runs_estimate,
        game.home_team.abbreviation,
        game.away_team.abbreviation,
    )
    block = AsianHandicapBlock(
        home=AsianHandicapSideOut.model_validate(ah_raw["home"]),
        away=AsianHandicapSideOut.model_validate(ah_raw["away"]),
    )
    return out.model_copy(update={"asian_handicap": block})


async def compute_prediction_response(
    session: AsyncSession,
    svc: MlbPredictionService,
    game_pk: int,
) -> PredictionResponse:
    result = await session.execute(
        select(Game)
        .where(Game.game_pk == game_pk)
        .options(selectinload(Game.weather), selectinload(Game.home_team), selectinload(Game.away_team)),
    )
    game = result.scalar_one_or_none()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.home_team is None or game.away_team is None:
        raise HTTPException(status_code=500, detail="Partido sin datos de equipos.")
    snap_row = await session.execute(
        select(GameFeatureSnapshot).where(GameFeatureSnapshot.game_pk == game_pk)
    )
    snapshot = snap_row.scalar_one_or_none()
    pr = svc.predict(game, game.weather, snapshot)
    return prediction_response_from_result(
        pr,
        home_abbr=game.home_team.abbreviation,
        away_abbr=game.away_team.abbreviation,
    )
