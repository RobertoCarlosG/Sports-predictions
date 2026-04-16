import json
from pathlib import Path

from app.data.mlb_team_abbreviations import team_abbr_for_display
from app.services.mlb_client import parse_schedule_games, team_abbreviation


def test_parse_schedule_games_extracts_game() -> None:
    raw = json.loads(
        (Path(__file__).parent / "fixtures" / "schedule_sample.json").read_text(encoding="utf-8")
    )
    games = parse_schedule_games(raw)
    assert len(games) == 1
    g = games[0]
    assert g["game_pk"] == 717715
    assert g["home_team_id"] == 147
    assert g["away_team_id"] == 139
    assert g["home_team_abbr"] == "NYY"
    assert g["away_team_abbr"] == "TB"
    assert g["home_score"] == 5
    assert g["away_score"] == 3
    assert g["venue_id"] == 3289


def test_team_abbreviation_fallback_file_code() -> None:
    assert team_abbreviation({"fileCode": "chc"}) == "CHC"


def test_team_abbreviation_fallback_nickname_from_name() -> None:
    assert team_abbreviation({"name": "Chicago Cubs"}) == "CUBS"


def test_team_abbreviation_unknown() -> None:
    assert team_abbreviation({}) == "?"


def test_team_abbr_map_overrides_bad_placeholder() -> None:
    assert team_abbr_for_display(147, "HOME", "New York Yankees") == "NYY"
    assert team_abbr_for_display(110, "AWAY", "Baltimore Orioles") == "BAL"


def test_team_abbr_float_id_matches_int_key() -> None:
    """110.0 in {110: 'BAL'} es False en Python; el lookup debe normalizar."""
    assert team_abbr_for_display(110.0, "HOME", "") == "BAL"
