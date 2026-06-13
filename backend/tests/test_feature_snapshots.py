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


def _make_game(game_pk: int, game_date: dt.date) -> Game:
    return Game(
        game_pk=game_pk,
        season="2025",
        game_date=game_date,
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


def test_should_persist_snapshot_within_date_range() -> None:
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    g = _make_game(10, dt.date(2025, 4, 15))
    assert _should_persist_snapshot(
        g, season=None, today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )


def test_should_not_persist_snapshot_before_date_range() -> None:
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    g = _make_game(11, dt.date(2025, 4, 5))
    assert not _should_persist_snapshot(
        g, season=None, today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )


def test_should_not_persist_snapshot_after_date_range() -> None:
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    g = _make_game(12, dt.date(2025, 4, 25))
    assert not _should_persist_snapshot(
        g, season=None, today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )


def test_date_range_takes_precedence_over_season() -> None:
    """start_date/end_date should override season-based filtering."""
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    # Game is season 2024 (would normally be excluded by season="2025")
    g = Game(
        game_pk=13,
        season="2024",
        game_date=dt.date(2025, 4, 12),
        game_datetime_utc=None,
        status="Final",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=3,
        away_score=2,
        lineups_json=None,
        boxscore_json=None,
    )
    assert _should_persist_snapshot(
        g, season="2025", today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )
