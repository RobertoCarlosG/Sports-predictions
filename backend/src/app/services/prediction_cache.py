from __future__ import annotations

import datetime as dt

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mlb import Game, GamePredictionCache
from app.schemas.games import PredictionResponse


def ml_pick_from_home_win_probability(p_home: float) -> str:
    """Lado del Moneyline: conviene derivar siempre de la probabilidad (fuente de verdad en BD)."""
    return "home" if p_home > 0.5 else "away"


def _is_final_status_for_eval(status: str) -> bool:
    s = status.lower()
    return any(x in s for x in ("final", "completed", "game over"))


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
        predicted_winner=row.predicted_winner,
        actual_winner=row.actual_winner,
        is_correct=row.is_correct,
        evaluated_at=row.evaluated_at.isoformat() if row.evaluated_at else None,
    )


async def upsert_prediction_cache(
    session: AsyncSession,
    response: PredictionResponse,
    trigger_reason: str | None,
) -> None:
    now = dt.datetime.now(dt.UTC)
    row = await session.get(GamePredictionCache, response.game_pk)

    predicted_winner = ml_pick_from_home_win_probability(response.home_win_probability)
    
    if row is None:
        row = GamePredictionCache(
            game_pk=response.game_pk,
            home_win_probability=response.home_win_probability,
            total_runs_estimate=response.total_runs_estimate,
            over_under_line=response.over_under_line,
            model_version=response.model_version,
            trigger_reason=trigger_reason,
            computed_at=now,
            predicted_winner=predicted_winner,
        )
        session.add(row)
    else:
        row.home_win_probability = response.home_win_probability
        row.total_runs_estimate = response.total_runs_estimate
        row.over_under_line = response.over_under_line
        row.model_version = response.model_version
        row.trigger_reason = trigger_reason
        row.computed_at = now
        row.predicted_winner = predicted_winner


async def evaluate_prediction(
    session: AsyncSession,
    game_pk: int,
) -> bool:
    """
    Evalúa una predicción contra el resultado real del juego.
    Retorna True si se evaluó correctamente, False si no hay datos suficientes.
    """
    result = await session.execute(
        select(Game).where(Game.game_pk == game_pk)
    )
    game = result.scalar_one_or_none()
    
    if game is None:
        return False
    
    if game.home_score is None or game.away_score is None:
        return False
    
    if not _is_final_status_for_eval(game.status):
        return False

    pred_row = await session.get(GamePredictionCache, game_pk)

    if pred_row is None:
        return False

    if game.home_score > game.away_score:
        actual_winner = "home"
    elif game.away_score > game.home_score:
        actual_winner = "away"
    else:
        actual_winner = "tie"

    # Siempre alinear con home_win_probability (evita cadenas raras, mayúsculas o desincronización).
    pred_side = ml_pick_from_home_win_probability(float(pred_row.home_win_probability))
    pred_row.predicted_winner = pred_side
    is_correct = pred_side == actual_winner

    pred_row.actual_winner = actual_winner
    pred_row.is_correct = is_correct
    pred_row.evaluated_at = dt.datetime.now(dt.UTC)

    return True


async def recompute_all_moneyline_evaluations(session: AsyncSession) -> tuple[int, int]:
    """
    Vuelve a evaluar Moneyline para todas las filas con marcador (p. ej. tras corregir la lógica).
    Devuelve (partidos_reevaluados, aciertos).
    """
    result = await session.execute(
        select(GamePredictionCache.game_pk)
        .join(Game, Game.game_pk == GamePredictionCache.game_pk)
        .where(
            Game.home_score.is_not(None),
            Game.away_score.is_not(None),
        )
    )
    pks = list(result.scalars().all())
    updated = 0
    correct = 0
    for pk in pks:
        if await evaluate_prediction(session, int(pk)):
            updated += 1
            refreshed = await session.get(GamePredictionCache, int(pk))
            if refreshed and refreshed.is_correct:
                correct += 1
    return updated, correct


async def evaluate_all_pending_predictions(
    session: AsyncSession,
) -> tuple[int, int]:
    """
    Evalúa todas las predicciones que tienen un juego finalizado pero aún no han sido evaluadas.
    Retorna (total_evaluados, total_correctos).
    """
    result = await session.execute(
        select(GamePredictionCache)
        .where(GamePredictionCache.evaluated_at.is_(None))
    )
    pending = result.scalars().all()
    
    evaluated_count = 0
    correct_count = 0
    
    for pred in pending:
        if await evaluate_prediction(session, pred.game_pk):
            evaluated_count += 1
            refreshed = await session.get(GamePredictionCache, pred.game_pk)
            if refreshed and refreshed.is_correct:
                correct_count += 1
    
    return evaluated_count, correct_count


async def clear_prediction_cache(session: AsyncSession) -> int:
    res = await session.execute(delete(GamePredictionCache))
    return res.rowcount or 0
