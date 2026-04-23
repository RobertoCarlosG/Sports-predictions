from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mlb import Game, GameFeatureSnapshot


def is_final_game_status(status: str) -> bool:
    s = status.lower()
    return (
        "final" in s
        or "completed" in s
        or "game over" in s
        or s in {"final", "completed"}
    )


def game_has_final_scores(game: Game) -> bool:
    return (
        game.home_score is not None
        and game.away_score is not None
        and is_final_game_status(game.status)
    )


def _rolling_win_rate_and_runs(
    history: Sequence[tuple[bool, int]],
    window: int,
) -> tuple[float, float]:
    """Últimos `window` partidos del equipo: tasa de victorias y media de carreras anotadas."""
    if not history or window < 1:
        return 0.5, 4.5
    tail = list(history[-window:])
    n = len(tail)
    wins = sum(1 for won, _ in tail if won)
    runs_for = [r for _, r in tail]
    return wins / n, sum(runs_for) / n


async def rebuild_game_feature_snapshots(
    session: AsyncSession,
    *,
    rolling_window: int = 10,
    season: str | None = None,
) -> int:
    """Recalcula filas en `game_feature_snapshots`.

    Recorre **todos** los partidos (todas las temporadas) en orden cronológico para que
    las rachas rodantes tengan contexto previo. Si ``season`` está fijado, solo se borran y
    reescriben snapshots de esa temporada; el resto de partidos solo alimenta el historial.

    - `home_win` / `total_runs` solo para partidos finalizados con marcador.
    Devuelve el número de filas escritas.
    """
    stmt = (
        select(Game)
        .options(selectinload(Game.weather))
        .order_by(Game.game_date, Game.game_pk)
    )
    result = await session.execute(stmt)
    games = result.scalars().unique().all()

    team_history: dict[int, list[tuple[bool, int]]] = defaultdict(list)

    if season is not None:
        await session.execute(
            delete(GameFeatureSnapshot).where(
                GameFeatureSnapshot.game_pk.in_(select(Game.game_pk).where(Game.season == season))
            )
        )
    else:
        await session.execute(delete(GameFeatureSnapshot))

    count = 0
    persist_season = season
    for g in games:
        home_hist = team_history[g.home_team_id]
        away_hist = team_history[g.away_team_id]
        hw_roll, hra_roll = _rolling_win_rate_and_runs(home_hist, rolling_window)
        aw_roll, ara_roll = _rolling_win_rate_and_runs(away_hist, rolling_window)

        w = g.weather
        temp = float(w.temperature_c) if w and w.temperature_c is not None else None
        hum = float(w.humidity_pct) if w and w.humidity_pct is not None else None
        wind = float(w.wind_speed_mps) if w and w.wind_speed_mps is not None else None
        elev = float(w.elevation_m) if w and w.elevation_m is not None else None

        home_win: int | None = None
        total_runs: float | None = None
        if game_has_final_scores(g):
            assert g.home_score is not None and g.away_score is not None
            home_win = 1 if g.home_score > g.away_score else 0
            total_runs = float(g.home_score + g.away_score)

        if persist_season is None or g.season == persist_season:
            row = GameFeatureSnapshot(
                game_pk=g.game_pk,
                home_wins_roll=hw_roll,
                away_wins_roll=aw_roll,
                home_runs_avg_roll=hra_roll,
                away_runs_avg_roll=ara_roll,
                temperature_c=temp,
                humidity_pct=hum,
                wind_speed_mps=wind,
                elevation_m=elev,
                home_win=home_win,
                total_runs=total_runs,
                feature_vector_json=None,
            )
            session.add(row)
            count += 1

        if game_has_final_scores(g):
            assert g.home_score is not None and g.away_score is not None
            home_won = g.home_score > g.away_score
            home_hist.append((home_won, g.home_score))
            away_hist.append((not home_won, g.away_score))

    await session.flush()
    return count
