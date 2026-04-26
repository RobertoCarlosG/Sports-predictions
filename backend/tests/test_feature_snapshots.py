import datetime as dt

from app.models.mlb import Game
from app.services.feature_snapshots import (
    _rolling_win_rate_and_runs,
    _should_persist_snapshot,
    game_has_final_scores,
    is_final_game_status,
)


def test_is_final_game_status() -> None:
    assert is_final_game_status("Final")
    assert is_final_game_status("Game Over")
    assert not is_final_game_status("Preview")


def test_game_has_final_scores() -> None:
    g = Game(
        game_pk=1,
        season="2025",
        game_date=dt.date(2025, 4, 1),
        game_datetime_utc=None,
        status="Final",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=5,
        away_score=3,
        lineups_json=None,
        boxscore_json=None,
    )
    assert game_has_final_scores(g)


def test_rolling_win_rate_and_runs() -> None:
    w, r = _rolling_win_rate_and_runs([], 10)
    assert w == 0.5 and r == 4.5
    hist = [(True, 5), (False, 2), (True, 6)]
    w2, r2 = _rolling_win_rate_and_runs(hist, 10)
    assert w2 == 2 / 3
    assert abs(r2 - (5 + 2 + 6) / 3) < 1e-9


def test_should_persist_upcoming_snapshot_even_outside_requested_season() -> None:
    today = dt.date(2026, 4, 26)
    g = Game(
        game_pk=2,
        season="2026",
        game_date=today + dt.timedelta(days=1),
        game_datetime_utc=None,
        status="Scheduled",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=None,
        away_score=None,
        lineups_json=None,
        boxscore_json=None,
    )
    assert _should_persist_snapshot(g, season="2025", today=today, upcoming_snapshot_days=1)


def test_should_not_persist_non_upcoming_snapshot_outside_requested_season() -> None:
    today = dt.date(2026, 4, 26)
    g = Game(
        game_pk=3,
        season="2026",
        game_date=today + dt.timedelta(days=2),
        game_datetime_utc=None,
        status="Scheduled",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=None,
        away_score=None,
        lineups_json=None,
        boxscore_json=None,
    )
    assert not _should_persist_snapshot(g, season="2025", today=today, upcoming_snapshot_days=1)
