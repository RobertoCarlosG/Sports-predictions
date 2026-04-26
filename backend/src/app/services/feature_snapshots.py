from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Sequence
from itertools import groupby

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mlb import Game, GameFeatureSnapshot
from app.services.mlb_client import MlbApiClient
from app.services.mlb_sync import starters_from_boxscore
from app.services.pitching_stats import game_pitching_feature_values

UPCOMING_SNAPSHOT_DAYS = 1


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


def _game_starter_ids(g: Game) -> tuple[int | None, int | None]:
    h, a = g.home_starter_id, g.away_starter_id
    if g.boxscore_json:
        bh, ba = starters_from_boxscore(g.boxscore_json)
        h = h if h is not None else bh
        a = a if a is not None else ba
    return h, a


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


def _should_persist_snapshot(
    game: Game,
    *,
    season: str | None,
    today: dt.date,
    upcoming_snapshot_days: int,
) -> bool:
    """Persist target season plus today's/tomorrow's scheduled games for live inference."""
    if season is None or game.season == season:
        return True
    upcoming_end = today + dt.timedelta(days=upcoming_snapshot_days)
    return today <= game.game_date <= upcoming_end


async def rebuild_game_feature_snapshots(
    session: AsyncSession,
    *,
    rolling_window: int = 10,
    season: str | None = None,
    mlb: MlbApiClient | None = None,
    upcoming_snapshot_days: int = UPCOMING_SNAPSHOT_DAYS,
) -> int:
    """Recalcula filas en `game_feature_snapshots`.

    Recorre **todos** los partidos (todas las temporadas) en orden cronológico para que
    las rachas rodantes tengan contexto previo. Si ``season`` está fijado, solo se borran y
    reescriben snapshots de esa temporada; el resto de partidos solo alimenta el historial.

    - `home_win` / `total_runs` solo para partidos finalizados con marcador.
    - ERA de abridores y del staff (proxy «bullpen») si ``mlb`` está disponible; si no, se usan
      valores por defecto (ver ``pitching_stats``).
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

    today = dt.datetime.now(dt.UTC).date()

    if season is not None:
        upcoming_end = today + dt.timedelta(days=upcoming_snapshot_days)
        await session.execute(
            delete(GameFeatureSnapshot).where(
                GameFeatureSnapshot.game_pk.in_(
                    select(Game.game_pk).where(
                        or_(
                            Game.season == season,
                            Game.game_date.between(today, upcoming_end),
                        )
                    )
                )
            )
        )
    else:
        await session.execute(delete(GameFeatureSnapshot))

    count = 0
    for _game_date, day_games_iter in groupby(games, key=lambda game: game.game_date):
        day_games = list(day_games_iter)

        # Snapshot features for every game on this date are computed from history
        # available before this date. Today's games never see today's earlier finals.
        for g in day_games:
            if not _should_persist_snapshot(
                g,
                season=season,
                today=today,
                upcoming_snapshot_days=upcoming_snapshot_days,
            ):
                continue

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

            h_sid, a_sid = _game_starter_ids(g)
            hse, ase, hbe, abe = await game_pitching_feature_values(
                session,
                mlb,
                season=str(g.season),
                home_team_id=g.home_team_id,
                away_team_id=g.away_team_id,
                home_starter_id=h_sid,
                away_starter_id=a_sid,
                commit_before_mlb=True,
            )

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
                home_starter_era=hse,
                away_starter_era=ase,
                home_bullpen_era=hbe,
                away_bullpen_era=abe,
                home_win=home_win,
                total_runs=total_runs,
                feature_vector_json=None,
            )
            session.add(row)
            count += 1

        for g in day_games:
            if game_has_final_scores(g):
                assert g.home_score is not None and g.away_score is not None
                home_won = g.home_score > g.away_score
                team_history[g.home_team_id].append((home_won, g.home_score))
                team_history[g.away_team_id].append((not home_won, g.away_score))

    await session.flush()
    return count
