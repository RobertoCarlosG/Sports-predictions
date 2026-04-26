from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from collections import defaultdict
from typing import Literal

from app.schemas.backtest import (
    BacktestGameRow,
    BacktestResponse,
    BacktestSummary,
    BacktestTimePoint,
    OUUserOutcome,
)

WinnerSide = Literal["home", "away", "tie"]


def is_final_game_status(status: str) -> bool:
    s = status.lower()
    return any(x in s for x in ("final", "completed", "game over"))


def side_probability(home_win_probability: float) -> float:
    return max(home_win_probability, 1.0 - home_win_probability)


def predicted_winner_from_p_home(p_home: float) -> Literal["home", "away"]:
    return "home" if p_home > 0.5 else "away"


def actual_winner_from_scores(home_score: int, away_score: int) -> WinnerSide:
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "tie"


def predicted_ou_from_estimates(total_runs_estimate: float, over_under_line: float) -> Literal["over", "under"]:
    return "over" if total_runs_estimate > over_under_line else "under"


def actual_ou_label(total_runs: int, line: float) -> Literal["over", "under", "push"]:
    t = float(total_runs)
    if t > line:
        return "over"
    if t < line:
        return "under"
    return "push"


def resolve_ou_user_outcome(
    predicted: Literal["over", "under"],
    total_runs: int,
    line: float,
) -> tuple[OUUserOutcome, bool | None]:
    act = actual_ou_label(total_runs, line)
    if act == "push":
        return "push", None
    if predicted == act:
        return "win", True
    return "loss", False


@dataclass
class BacktestRowInputs:
    game_pk: int
    game_date: dt.date
    game_datetime_utc: dt.datetime | None
    away_abbr: str
    home_abbr: str
    home_win_probability: float
    over_under_line: float
    total_runs_estimate: float
    predicted_winner: str | None
    actual_winner: str | None
    is_correct: bool | None
    home_score: int
    away_score: int


def _success_label(ml_correct: bool, ou_out: OUUserOutcome) -> str:
    if ou_out == "push":
        return f"{'1' if ml_correct else '0'}/1 + Push O/U"
    sc = (1 if ml_correct else 0) + (1 if ou_out == "win" else 0)
    return f"{sc}/2 Aciertos"


def build_backtest_game_row(r: BacktestRowInputs) -> BacktestGameRow:
    p_home = r.home_win_probability
    if r.predicted_winner in ("home", "away"):
        pred_w: Literal["home", "away"] = r.predicted_winner  # type: ignore[assignment]
    else:
        pred_w = predicted_winner_from_p_home(p_home)

    if r.actual_winner in ("home", "away", "tie"):
        act_w: WinnerSide = r.actual_winner  # type: ignore[assignment]
    else:
        act_w = actual_winner_from_scores(r.home_score, r.away_score)

    if r.is_correct is not None:
        ml_correct = bool(r.is_correct)
    else:
        ml_correct = pred_w == act_w and act_w != "tie"

    pred_ou = predicted_ou_from_estimates(r.total_runs_estimate, r.over_under_line)
    total = r.home_score + r.away_score
    ou_out, ou_ok = resolve_ou_user_outcome(pred_ou, total, r.over_under_line)

    success_count = (1 if ml_correct else 0) + (1 if ou_ok is True else 0)
    success_label = _success_label(ml_correct, ou_out)

    matchup = f"{r.away_abbr} @ {r.home_abbr}"
    return BacktestGameRow(
        game_pk=r.game_pk,
        game_date=r.game_date,
        game_datetime_utc=r.game_datetime_utc,
        away_abbr=r.away_abbr,
        home_abbr=r.home_abbr,
        matchup_label=matchup,
        p_home=p_home,
        ml_confidence=side_probability(p_home),
        predicted_winner=pred_w,
        actual_winner=act_w,
        ml_correct=ml_correct,
        over_under_line=r.over_under_line,
        total_runs_estimate=r.total_runs_estimate,
        predicted_ou=pred_ou,
        total_runs_actual=total,
        ou_outcome=ou_out,
        ou_correct=ou_ok,
        success_count=success_count,
        success_label=success_label,
    )


def build_summary(games: list[BacktestGameRow]) -> BacktestSummary:
    n = len(games)
    if n == 0:
        return BacktestSummary(
            n_games=0,
            ml_wins=0,
            ml_losses=0,
            ou_wins=0,
            ou_losses=0,
            ou_pushes=0,
            global_hit_rate_pct=None,
            total_decided_picks=0,
            total_correct_picks=0,
        )

    ml_w = sum(1 for g in games if g.ml_correct)
    ml_l = n - ml_w
    ou_w = sum(1 for g in games if g.ou_outcome == "win")
    ou_l = sum(1 for g in games if g.ou_outcome == "loss")
    ou_p = sum(1 for g in games if g.ou_outcome == "push")

    decided_ou = n - ou_p
    total_picks = n + decided_ou
    total_correct = ml_w + ou_w
    ghr = (total_correct / total_picks * 100.0) if total_picks else None

    return BacktestSummary(
        n_games=n,
        ml_wins=ml_w,
        ml_losses=ml_l,
        ou_wins=ou_w,
        ou_losses=ou_l,
        ou_pushes=ou_p,
        global_hit_rate_pct=round(ghr, 2) if ghr is not None else None,
        total_decided_picks=total_picks,
        total_correct_picks=total_correct,
    )


def build_timeseries(
    games: list[BacktestGameRow],
    date_from: dt.date,
    date_to: dt.date,
    skip_empty_days: bool,
) -> list[BacktestTimePoint]:
    by_day: dict[dt.date, list[BacktestGameRow]] = defaultdict(list)
    for g in games:
        by_day[g.game_date].append(g)

    def point_for(d: dt.date) -> BacktestTimePoint:
        day_g = by_day.get(d, [])
        c = len(day_g)
        if c == 0:
            return BacktestTimePoint(
                game_date=d,
                games_count=0,
                ml_hit_rate_pct=None,
                ou_hit_rate_pct=None,
                ou_decided=0,
            )
        ml_hits = sum(1 for x in day_g if x.ml_correct)
        ou_dec = [x for x in day_g if x.ou_outcome != "push"]
        ou_hits = sum(1 for x in ou_dec if x.ou_correct is True)
        decided = len(ou_dec)
        return BacktestTimePoint(
            game_date=d,
            games_count=c,
            ml_hit_rate_pct=round(ml_hits / c * 100.0, 2),
            ou_hit_rate_pct=round(ou_hits / decided * 100.0, 2) if decided else None,
            ou_decided=decided,
        )

    if skip_empty_days:
        return sorted(
            (point_for(d) for d in by_day),
            key=lambda p: p.game_date,
        )

    out: list[BacktestTimePoint] = []
    d = date_from
    one = dt.timedelta(days=1)
    while d <= date_to:
        out.append(point_for(d))
        d = d + one
    return out
