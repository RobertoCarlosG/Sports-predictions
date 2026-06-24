"""Recalcula `nba_game_feature_snapshots` (espeja services/feature_snapshots.py).

Recorre los partidos en orden cronológico para que las rachas tengan contexto
previo. Calcula métricas avanzadas (net rating, pace, eFG%) por partido a partir
de `nba_games.boxscore_json` y deriva descanso / back-to-back del calendario.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from dataclasses import dataclass
from itertools import groupby
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.nba import NbaGame, NbaGameFeatureSnapshot

log = logging.getLogger(__name__)


def is_final_game_status(status: str) -> bool:
    s = (status or "").lower()
    return "final" in s or "completed" in s or "game over" in s


def game_has_final_scores(game: NbaGame) -> bool:
    return game.home_score is not None and game.away_score is not None and is_final_game_status(game.status)


@dataclass
class _TeamGame:
    won: bool
    pts_for: float
    pts_against: float
    net_rating: float | None
    pace: float | None
    efg: float | None
    game_date: dt.date


def _possessions(stats: dict[str, Any]) -> float | None:
    try:
        fga = float(stats.get("FGA", 0))
        fta = float(stats.get("FTA", 0))
        oreb = float(stats.get("OREB", 0))
        tov = float(stats.get("TOV", 0))
    except (TypeError, ValueError):
        return None
    poss = fga + 0.44 * fta - oreb + tov
    return poss if poss > 0 else None


def _efg(stats: dict[str, Any]) -> float | None:
    try:
        fgm = float(stats.get("FGM", 0))
        fg3m = float(stats.get("FG3M", 0))
        fga = float(stats.get("FGA", 0))
    except (TypeError, ValueError):
        return None
    if fga <= 0:
        return None
    return (fgm + 0.5 * fg3m) / fga


def _advanced_for_side(
    side_stats: dict[str, Any] | None,
    opp_stats: dict[str, Any] | None,
    pts_for: float,
    pts_against: float,
) -> tuple[float | None, float | None, float | None]:
    """(net_rating, pace, efg) para un equipo en un partido; None si faltan stats."""
    if not side_stats:
        return None, None, None
    poss = _possessions(side_stats)
    opp_poss = _possessions(opp_stats) if opp_stats else poss
    if poss is None:
        return None, None, _efg(side_stats)
    off_rating = 100.0 * pts_for / poss
    def_rating = 100.0 * pts_against / (opp_poss if opp_poss else poss)
    net = off_rating - def_rating
    pace = poss
    return net, pace, _efg(side_stats)


def _roll_avg(values: list[float | None], window: int) -> float | None:
    tail = [v for v in values[-window:] if v is not None]
    if not tail:
        return None
    return sum(tail) / len(tail)


def _rolling_features(history: list[_TeamGame], window: int) -> dict[str, float | None]:
    if not history:
        return {
            "win_pct": None,
            "pts_for": None,
            "pts_against": None,
            "net_rating": None,
            "pace": None,
            "efg": None,
        }
    tail = history[-window:]
    n = len(tail)
    return {
        "win_pct": sum(1 for g in tail if g.won) / n,
        "pts_for": sum(g.pts_for for g in tail) / n,
        "pts_against": sum(g.pts_against for g in tail) / n,
        "net_rating": _roll_avg([g.net_rating for g in tail], window),
        "pace": _roll_avg([g.pace for g in tail], window),
        "efg": _roll_avg([g.efg for g in tail], window),
    }


def _rest_and_b2b(last_date: dt.date | None, game_date: dt.date) -> tuple[int | None, int | None]:
    if last_date is None:
        return None, None
    rest = (game_date - last_date).days
    return rest, (1 if rest == 1 else 0)


async def rebuild_nba_game_feature_snapshots(
    session: AsyncSession,
    *,
    rolling_window: int = 10,
    season: str | None = None,
) -> int:
    """Recalcula filas en `nba_game_feature_snapshots`. Devuelve filas escritas.

    Carga todos los partidos en orden cronológico (para que las rachas tengan
    contexto previo) pero solo borra/persiste snapshots de la temporada objetivo
    cuando se pasa ``season``.
    """
    stmt = select(NbaGame).order_by(NbaGame.game_date, NbaGame.game_id)

    if season is not None and season != "all":
        await session.execute(
            delete(NbaGameFeatureSnapshot).where(
                NbaGameFeatureSnapshot.game_id.in_(select(NbaGame.game_id).where(NbaGame.season == season))
            )
        )
    else:
        await session.execute(delete(NbaGameFeatureSnapshot))

    result = await session.execute(stmt)
    games = result.scalars().all()

    team_history: dict[int, list[_TeamGame]] = defaultdict(list)
    last_played: dict[int, dt.date] = {}
    count = 0

    for _gd, day_iter in groupby(games, key=lambda g: g.game_date):
        day_games = list(day_iter)
        for g in day_games:
            persist = season is None or season == "all" or g.season == season
            if persist:
                hr = _rolling_features(team_history[g.home_team_id], rolling_window)
                ar = _rolling_features(team_history[g.away_team_id], rolling_window)
                h_rest, h_b2b = _rest_and_b2b(last_played.get(g.home_team_id), g.game_date)
                a_rest, a_b2b = _rest_and_b2b(last_played.get(g.away_team_id), g.game_date)

                home_win: int | None = None
                margin: float | None = None
                total_points: float | None = None
                if game_has_final_scores(g):
                    assert g.home_score is not None and g.away_score is not None
                    home_win = 1 if g.home_score > g.away_score else 0
                    margin = float(g.home_score - g.away_score)
                    total_points = float(g.home_score + g.away_score)

                session.add(
                    NbaGameFeatureSnapshot(
                        game_id=g.game_id,
                        home_win_pct_roll=hr["win_pct"],
                        away_win_pct_roll=ar["win_pct"],
                        home_pts_for_roll=hr["pts_for"],
                        away_pts_for_roll=ar["pts_for"],
                        home_pts_against_roll=hr["pts_against"],
                        away_pts_against_roll=ar["pts_against"],
                        home_net_rating_roll=hr["net_rating"],
                        away_net_rating_roll=ar["net_rating"],
                        home_pace_roll=hr["pace"],
                        away_pace_roll=ar["pace"],
                        home_efg_roll=hr["efg"],
                        away_efg_roll=ar["efg"],
                        home_rest_days=h_rest,
                        away_rest_days=a_rest,
                        home_is_b2b=h_b2b,
                        away_is_b2b=a_b2b,
                        home_win=home_win,
                        margin=margin,
                        total_points=total_points,
                        feature_vector_json=None,
                    )
                )
                count += 1

        # Tras procesar el día, alimentar historial/calendario con los finalizados.
        for g in day_games:
            if not game_has_final_scores(g):
                continue
            assert g.home_score is not None and g.away_score is not None
            home_won = g.home_score > g.away_score
            box = g.boxscore_json or {}
            home_stats = box.get("home") if isinstance(box, dict) else None
            away_stats = box.get("away") if isinstance(box, dict) else None
            h_net, h_pace, h_efg = _advanced_for_side(home_stats, away_stats, float(g.home_score), float(g.away_score))
            a_net, a_pace, a_efg = _advanced_for_side(away_stats, home_stats, float(g.away_score), float(g.home_score))
            team_history[g.home_team_id].append(
                _TeamGame(
                    home_won,
                    float(g.home_score),
                    float(g.away_score),
                    h_net,
                    h_pace,
                    h_efg,
                    g.game_date,
                )
            )
            team_history[g.away_team_id].append(
                _TeamGame(
                    not home_won,
                    float(g.away_score),
                    float(g.home_score),
                    a_net,
                    a_pace,
                    a_efg,
                    g.game_date,
                )
            )
            last_played[g.home_team_id] = g.game_date
            last_played[g.away_team_id] = g.game_date

    await session.flush()
    return count
