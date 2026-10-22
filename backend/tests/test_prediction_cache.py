import datetime as dt

import pytest
from sqlalchemy import event, select

from app.models.mlb import Game, GamePredictionCache, Team
from app.services.prediction_cache import (
    evaluate_all_pending_predictions,
    ml_pick_from_home_win_probability,
    recompute_all_moneyline_evaluations,
)


def test_ml_pick_from_home_win_probability() -> None:
    assert ml_pick_from_home_win_probability(0.51) == "home"
    assert ml_pick_from_home_win_probability(0.50) == "away"
    assert ml_pick_from_home_win_probability(0.49) == "away"


async def _seed_predictions(session) -> None:  # type: ignore[no-untyped-def]
    session.add_all([Team(id=1, name="Home", abbreviation="HOM"), Team(id=2, name="Away", abbreviation="AWY")])
    # (pk, status, home, away, p_home): 1 acierto local, 1 fallo, 1 sin final, 1 sin marcador.
    rows = [
        (1, "Final", 5, 2, 0.7),
        (2, "Final", 1, 4, 0.6),
        (3, "In Progress", 3, 1, 0.6),
        (4, "Scheduled", None, None, 0.6),
    ]
    for pk, status, hs, as_, p in rows:
        session.add(
            Game(
                game_pk=pk,
                season="2026",
                game_date=dt.date(2026, 9, 1),
                status=status,
                home_team_id=1,
                away_team_id=2,
                home_score=hs,
                away_score=as_,
                boxscore_json={"big": "x" * 1000},
            )
        )
        session.add(
            GamePredictionCache(
                game_pk=pk,
                home_win_probability=p,
                total_runs_estimate=8.0,
                over_under_line=8.5,
                model_version="xgb-test",
            )
        )
    await session.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("fn", [evaluate_all_pending_predictions, recompute_all_moneyline_evaluations])
async def test_batch_evaluation_single_query(sqlite_session_factory, sqlite_engine, fn) -> None:  # type: ignore[no-untyped-def]
    async with sqlite_session_factory() as session:
        await _seed_predictions(session)

    statements: list[str] = []

    def _count(conn, cursor, statement, *args):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(sqlite_engine.sync_engine, "before_cursor_execute", _count)
    try:
        async with sqlite_session_factory() as session:
            evaluated, correct = await fn(session)
            await session.commit()
    finally:
        event.remove(sqlite_engine.sync_engine, "before_cursor_execute", _count)

    assert (evaluated, correct) == (2, 1)
    selects = [s for s in statements if s.lstrip().upper().startswith("SELECT")]
    assert len(selects) == 1, selects  # antes: 2–3 queries por fila
    assert "boxscore_json" not in selects[0]

    async with sqlite_session_factory() as session:
        by_pk = {r.game_pk: r for r in (await session.execute(select(GamePredictionCache))).scalars()}
    assert by_pk[1].is_correct is True and by_pk[1].actual_winner == "home"
    assert by_pk[2].is_correct is False and by_pk[2].actual_winner == "away"
    assert by_pk[3].evaluated_at is None and by_pk[4].evaluated_at is None
