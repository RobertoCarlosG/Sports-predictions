import datetime as dt

import pytest

from app.schemas.backtest import BacktestGameRow
from app.services.backtest import (
    BacktestRowInputs,
    actual_ou_label,
    build_backtest_game_row,
    build_summary,
    build_timeseries,
    is_final_game_status,
    resolve_ou_user_outcome,
    side_probability,
)


def test_side_probability() -> None:
    assert side_probability(0.55) == pytest.approx(0.55)
    assert side_probability(0.45) == pytest.approx(0.55)


def test_actual_ou_label() -> None:
    assert actual_ou_label(10, 8.5) == "over"
    assert actual_ou_label(5, 8.5) == "under"
    assert actual_ou_label(8, 8.0) == "push"
    # half-line: equality only on exact float match
    assert actual_ou_label(9, 8.5) == "over"


def test_resolve_ou_user_outcome() -> None:
    assert resolve_ou_user_outcome("over", 10, 8.5) == ("win", True)
    assert resolve_ou_user_outcome("under", 10, 8.5) == ("loss", False)
    assert resolve_ou_user_outcome("over", 8, 8.0) == ("push", None)


def test_is_final_game_status() -> None:
    assert is_final_game_status("Final")
    assert not is_final_game_status("In Progress")


def test_build_row_ml_and_ou() -> None:
    r = BacktestRowInputs(
        game_pk=1,
        game_date=dt.date(2024, 6, 1),
        game_datetime_utc=None,
        away_abbr="NYY",
        home_abbr="HOU",
        home_win_probability=0.6,
        over_under_line=8.5,
        total_runs_estimate=9.2,
        predicted_winner="home",
        actual_winner="home",
        is_correct=True,
        home_score=6,
        away_score=4,
    )
    g = build_backtest_game_row(r)
    assert g.ml_correct is True
    assert g.ou_outcome == "win"
    assert g.ou_correct is True
    assert g.total_runs_actual == 10
    assert g.success_label == "2/2 Aciertos"


def test_build_row_ou_push() -> None:
    r = BacktestRowInputs(
        game_pk=2,
        game_date=dt.date(2024, 6, 2),
        game_datetime_utc=None,
        away_abbr="A",
        home_abbr="B",
        home_win_probability=0.4,
        over_under_line=8.0,
        total_runs_estimate=7.0,
        predicted_winner="away",
        actual_winner="away",
        is_correct=True,
        home_score=4,
        away_score=4,
    )
    g = build_backtest_game_row(r)
    assert g.ou_outcome == "push"
    assert g.ou_correct is None
    assert "Push" in g.success_label


def test_build_summary_and_timeseries() -> None:
    games: list[BacktestGameRow] = []
    for i, (d, sc) in enumerate(
        [
            (dt.date(2024, 6, 1), "2/2 Aciertos"),
            (dt.date(2024, 6, 1), "2/2 Aciertos"),
            (dt.date(2024, 6, 2), "0/2 Aciertos"),
        ]
    ):
        games.append(
            BacktestGameRow(
                game_pk=i,
                game_date=d,
                game_datetime_utc=None,
                away_abbr="A",
                home_abbr="B",
                matchup_label="A @ B",
                p_home=0.5,
                ml_confidence=0.5,
                predicted_winner="home",
                actual_winner="home",
                ml_correct=sc.startswith("2"),
                over_under_line=8.5,
                total_runs_estimate=9.0,
                predicted_ou="over",
                total_runs_actual=10,
                ou_outcome="win" if sc.startswith("2") else "loss",
                ou_correct=sc.startswith("2"),
                success_count=2 if sc.startswith("2") else 0,
                success_label=sc,
            )
        )
    s = build_summary(games)
    assert s.n_games == 3
    assert s.total_correct_picks == s.ml_wins + s.ou_wins
    assert s.total_decided_picks == 2 * 3
    assert s.global_hit_rate_pct is not None

    ts = build_timeseries(games, dt.date(2024, 6, 1), dt.date(2024, 6, 2), skip_empty_days=True)
    assert len(ts) == 2
    ts2 = build_timeseries(games, dt.date(2024, 6, 1), dt.date(2024, 6, 3), skip_empty_days=False)
    # Inclusive: 1 Jun, 2 Jun, 3 Jun
    assert len(ts2) == 3
