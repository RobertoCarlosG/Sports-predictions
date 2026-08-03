"""Caché y evaluación de predicciones NBA (fork de services/prediction_cache.py)."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.nba_predictor import NbaPredictionResult
from app.models.nba import NbaGame, NbaGamePredictionCache
from app.schemas.nba import NbaPredictionResponse

log = logging.getLogger(__name__)


def _winner_from_probability(p_home: float) -> str:
    return "home" if p_home >= 0.5 else "away"


def prediction_response_from_result(result: NbaPredictionResult) -> NbaPredictionResponse:
    return NbaPredictionResponse(
        game_id=result.game_id,
        home_win_probability=result.home_win_probability,
        margin_estimate=result.margin_estimate,
        total_points_estimate=result.total_points_estimate,
        spread_line=result.spread_line,
        over_under_line=result.over_under_line,
        over_probability=result.over_probability,
        model_version=result.model_version,
        defaults_injected=result.defaults_injected,
        predicted_winner=_winner_from_probability(result.home_win_probability),
    )


async def get_cached_nba_prediction(
    session: AsyncSession,
    game_id: str,
    model_version: str,
) -> NbaPredictionResponse | None:
    row = (
        await session.execute(select(NbaGamePredictionCache).where(NbaGamePredictionCache.game_id == game_id))
    ).scalar_one_or_none()
    if row is None or row.model_version != model_version:
        return None
    return NbaPredictionResponse(
        game_id=row.game_id,
        home_win_probability=row.home_win_probability,
        margin_estimate=row.margin_estimate,
        total_points_estimate=row.total_points_estimate,
        spread_line=row.spread_line,
        over_under_line=row.over_under_line,
        over_probability=row.over_probability,
        model_version=row.model_version,
        defaults_injected=row.defaults_injected,
        predicted_winner=row.predicted_winner,
        actual_winner=row.actual_winner,
        is_correct=row.is_correct,
        evaluated_at=row.evaluated_at.isoformat() if row.evaluated_at else None,
    )


async def upsert_nba_prediction_cache(
    session: AsyncSession,
    response: NbaPredictionResponse,
    trigger_reason: str,
) -> None:
    row = (
        await session.execute(select(NbaGamePredictionCache).where(NbaGamePredictionCache.game_id == response.game_id))
    ).scalar_one_or_none()
    predicted_winner = response.predicted_winner or _winner_from_probability(response.home_win_probability)
    if row is None:
        session.add(
            NbaGamePredictionCache(
                game_id=response.game_id,
                home_win_probability=response.home_win_probability,
                margin_estimate=response.margin_estimate,
                total_points_estimate=response.total_points_estimate,
                spread_line=response.spread_line,
                over_under_line=response.over_under_line,
                over_probability=response.over_probability,
                model_version=response.model_version,
                defaults_injected=response.defaults_injected,
                trigger_reason=trigger_reason,
                predicted_winner=predicted_winner,
            )
        )
    else:
        row.home_win_probability = response.home_win_probability
        row.margin_estimate = response.margin_estimate
        row.total_points_estimate = response.total_points_estimate
        row.spread_line = response.spread_line
        row.over_under_line = response.over_under_line
        row.over_probability = response.over_probability
        row.model_version = response.model_version
        row.defaults_injected = response.defaults_injected
        row.trigger_reason = trigger_reason
        row.predicted_winner = predicted_winner
    await session.flush()


async def evaluate_nba_predictions_for_final_games(
    session: AsyncSession,
    games: Sequence[NbaGame],
) -> None:
    """Marca aciertos para partidos finalizados con predicción cacheada."""
    final = [
        g
        for g in games
        if g.home_score is not None and g.away_score is not None and "final" in (g.status or "").lower()
    ]
    if not final:
        return
    ids = [g.game_id for g in final]
    rows = (
        (await session.execute(select(NbaGamePredictionCache).where(NbaGamePredictionCache.game_id.in_(ids))))
        .scalars()
        .all()
    )
    by_id = {r.game_id: r for r in rows}
    now = dt.datetime.now(dt.UTC)
    for g in final:
        row = by_id.get(g.game_id)
        if row is None or row.predicted_winner is None:
            continue
        assert g.home_score is not None and g.away_score is not None
        actual = "home" if g.home_score > g.away_score else "away"
        row.actual_winner = actual
        row.is_correct = row.predicted_winner == actual
        row.evaluated_at = now
    await session.flush()
