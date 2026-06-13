"""Real SQLAlchemy model instances and Pydantic request bodies for integration tests.

All objects here are concrete instances — no MagicMock, no patches.
Factory functions return ORM objects ready to be added to a real PostgreSQL session.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

def make_team_la() -> dict[str, Any]:
    return dict(id=119, name="Los Angeles Dodgers", abbreviation="LAD", venue_id=22, venue_name="Dodger Stadium", league="NL", division="NL West")


def make_team_ny() -> dict[str, Any]:
    return dict(id=147, name="New York Yankees", abbreviation="NYY", venue_id=3289, venue_name="Yankee Stadium", league="AL", division="AL East")


def make_team_boston() -> dict[str, Any]:
    return dict(id=111, name="Boston Red Sox", abbreviation="BOS", venue_id=3, venue_name="Fenway Park", league="AL", division="AL East")


ALL_TEAMS = [make_team_la(), make_team_ny(), make_team_boston()]


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------

def make_game_scheduled() -> dict[str, Any]:
    """Upcoming game — no scores yet."""
    return dict(
        game_pk=748000,
        season="2025",
        game_date=dt.date(2025, 9, 15),
        game_datetime_utc=dt.datetime(2025, 9, 15, 20, 5, tzinfo=dt.UTC),
        status="Scheduled",
        home_team_id=119,   # LAD
        away_team_id=147,   # NYY
        venue_id=22,
        venue_name="Dodger Stadium",
        home_score=None,
        away_score=None,
        lineups_json=None,
        boxscore_json=None,
    )


def make_game_final_home_win() -> dict[str, Any]:
    """Completed game — home team won."""
    return dict(
        game_pk=748001,
        season="2025",
        game_date=dt.date(2025, 8, 10),
        game_datetime_utc=dt.datetime(2025, 8, 10, 22, 10, tzinfo=dt.UTC),
        status="Final",
        home_team_id=119,   # LAD
        away_team_id=147,   # NYY
        venue_id=22,
        venue_name="Dodger Stadium",
        home_score=7,
        away_score=3,
        lineups_json=None,
        boxscore_json=None,
    )


def make_game_final_away_win() -> dict[str, Any]:
    """Completed game — away team won."""
    return dict(
        game_pk=748002,
        season="2025",
        game_date=dt.date(2025, 8, 11),
        game_datetime_utc=dt.datetime(2025, 8, 11, 22, 10, tzinfo=dt.UTC),
        status="Final",
        home_team_id=119,   # LAD
        away_team_id=147,   # NYY
        venue_id=22,
        venue_name="Dodger Stadium",
        home_score=2,
        away_score=5,
        lineups_json=None,
        boxscore_json=None,
    )


def make_game_in_progress() -> dict[str, Any]:
    return dict(
        game_pk=748003,
        season="2025",
        game_date=dt.date(2025, 9, 14),
        game_datetime_utc=dt.datetime(2025, 9, 14, 23, 0, tzinfo=dt.UTC),
        status="In Progress",
        home_team_id=111,   # BOS
        away_team_id=119,   # LAD
        venue_id=3,
        venue_name="Fenway Park",
        home_score=3,
        away_score=2,
        lineups_json=None,
        boxscore_json=None,
    )


def make_game_postponed() -> dict[str, Any]:
    return dict(
        game_pk=748004,
        season="2025",
        game_date=dt.date(2025, 9, 16),
        game_datetime_utc=None,
        status="Postponed",
        home_team_id=111,   # BOS
        away_team_id=147,   # NYY
        venue_id=3,
        venue_name="Fenway Park",
        home_score=None,
        away_score=None,
        lineups_json=None,
        boxscore_json=None,
    )


ALL_GAMES = [
    make_game_scheduled(),
    make_game_final_home_win(),
    make_game_final_away_win(),
    make_game_in_progress(),
    make_game_postponed(),
]

# Map: game_pk → team IDs for convenience
GAME_PKS = [g["game_pk"] for g in ALL_GAMES]
SCHEDULED_GAME_PK = 748000
FINAL_HOME_WIN_PK = 748001
FINAL_AWAY_WIN_PK = 748002
IN_PROGRESS_PK = 748003
POSTPONED_PK = 748004


# ---------------------------------------------------------------------------
# GameWeather
# ---------------------------------------------------------------------------

def make_weather_dodger_stadium() -> dict[str, Any]:
    return dict(
        game_pk=748000,
        temperature_c=22.5,
        humidity_pct=45.0,
        wind_speed_mps=3.2,
        pressure_mbar=1015.0,
        elevation_m=52.0,
        raw_json=None,
        fetched_at=dt.datetime(2025, 9, 15, 10, 0, tzinfo=dt.UTC),
    )


def make_weather_yankee_stadium() -> dict[str, Any]:
    return dict(
        game_pk=748001,
        temperature_c=18.0,
        humidity_pct=65.0,
        wind_speed_mps=5.5,
        pressure_mbar=1012.0,
        elevation_m=10.0,
        raw_json=None,
        fetched_at=dt.datetime(2025, 8, 10, 10, 0, tzinfo=dt.UTC),
    )


ALL_WEATHER = [make_weather_dodger_stadium(), make_weather_yankee_stadium()]


# ---------------------------------------------------------------------------
# GameFeatureSnapshot
# ---------------------------------------------------------------------------

def make_snapshot_scheduled() -> dict[str, Any]:
    return dict(
        game_pk=748000,
        home_wins_roll=0.62,
        away_wins_roll=0.55,
        home_runs_avg_roll=4.8,
        away_runs_avg_roll=4.2,
        temperature_c=22.5,
        humidity_pct=45.0,
        wind_speed_mps=3.2,
        elevation_m=52.0,
        home_win=None,          # not played yet
        total_runs=None,
        home_starter_era=3.10,
        away_starter_era=3.75,
        home_bullpen_era=3.50,
        away_bullpen_era=3.80,
    )


def make_snapshot_final_home_win() -> dict[str, Any]:
    return dict(
        game_pk=748001,
        home_wins_roll=0.60,
        away_wins_roll=0.55,
        home_runs_avg_roll=5.1,
        away_runs_avg_roll=4.3,
        temperature_c=18.0,
        humidity_pct=65.0,
        wind_speed_mps=5.5,
        elevation_m=10.0,
        home_win=1,
        total_runs=10.0,
        home_starter_era=3.20,
        away_starter_era=4.10,
        home_bullpen_era=3.60,
        away_bullpen_era=3.90,
    )


def make_snapshot_final_away_win() -> dict[str, Any]:
    return dict(
        game_pk=748002,
        home_wins_roll=0.58,
        away_wins_roll=0.56,
        home_runs_avg_roll=4.5,
        away_runs_avg_roll=4.8,
        temperature_c=19.0,
        humidity_pct=60.0,
        wind_speed_mps=4.0,
        elevation_m=10.0,
        home_win=0,
        total_runs=7.0,
        home_starter_era=4.50,
        away_starter_era=3.10,
        home_bullpen_era=4.00,
        away_bullpen_era=3.20,
    )


ALL_SNAPSHOTS = [
    make_snapshot_scheduled(),
    make_snapshot_final_home_win(),
    make_snapshot_final_away_win(),
]


# ---------------------------------------------------------------------------
# AdminUser
# ---------------------------------------------------------------------------

ADMIN_USERNAME = "integration_admin"
ADMIN_PASSWORD = "int_test_P@ssw0rd!"
ADMIN_JWT_SECRET = "integration_test_jwt_secret_minimum_32_chars_long"


def make_admin_user_kwargs() -> dict[str, Any]:
    from app.core.admin_security import hash_password
    return dict(
        username=ADMIN_USERNAME,
        password_hash=hash_password(ADMIN_PASSWORD),
        is_active=True,
    )


# ---------------------------------------------------------------------------
# AppUser (requires PostgreSQL UUID generation)
# ---------------------------------------------------------------------------

APP_USER_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")
APP_USER_GOOGLE_ID = "google_integration_test_user_12345"
APP_USER_EMAIL = "integration_test@example.com"


def make_app_user_kwargs() -> dict[str, Any]:
    return dict(
        id=APP_USER_UUID,
        google_id=APP_USER_GOOGLE_ID,
        email=APP_USER_EMAIL,
        display_name="Integration Test User",
        picture_url=None,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# BetBank
# ---------------------------------------------------------------------------

def make_bet_bank_kwargs(user_id: uuid.UUID) -> dict[str, Any]:
    return dict(
        user_id=user_id,
        name="Test Bank",
        initial_amount=1000.0,
        currency="USD",
        is_active=True,
    )


# ---------------------------------------------------------------------------
# Request body payloads (Pydantic/dict, not ORM — for HTTP tests)
# ---------------------------------------------------------------------------

# Admin login
ADMIN_LOGIN_BODY = {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}
ADMIN_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"}

# Bet creation
BET_CREATE_BODY = {
    "bank_id": 1,           # will be set dynamically in tests
    "game_pk": SCHEDULED_GAME_PK,
    "bet_type": "moneyline",
    "bet_side": "home",
    "stake": 50.0,
    "odds": 1.85,
    "notes": "Integration test bet",
}

# BetBank creation
BET_BANK_CREATE_BODY = {
    "name": "Test Bank",
    "initial_amount": 1000.0,
    "currency": "USD",
}

# BetPeriod creation
BET_PERIOD_CREATE_BODY = {
    "bank_id": 1,           # will be set dynamically in tests
    "year": 2025,
    "month": 9,
}

# MLBSync range
MLB_SYNC_RANGE_BODY = {
    "start_date": "2025-08-10",
    "end_date": "2025-08-11",
    "fetch_details": False,
}
