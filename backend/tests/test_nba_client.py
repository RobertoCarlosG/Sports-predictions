"""Tests de parsing del cliente NBA (sin red)."""

from __future__ import annotations

from app.services.nba_client import parse_league_game_log, parse_scoreboard


def _team_row(game_id, team_id, name, abbr, matchup, wl, pts):
    return {
        "GAME_ID": game_id,
        "SEASON_ID": "22023",
        "TEAM_ID": team_id,
        "TEAM_NAME": name,
        "TEAM_ABBREVIATION": abbr,
        "GAME_DATE": "2023-10-24",
        "MATCHUP": matchup,
        "WL": wl,
        "PTS": pts,
        "FGM": 40,
        "FGA": 88,
        "FG3M": 12,
        "FTA": 20,
        "FTM": 16,
        "OREB": 10,
        "DREB": 33,
        "REB": 43,
        "TOV": 13,
        "AST": 24,
    }


def test_parse_league_game_log_pairs_home_away():
    rows = [
        _team_row("0022300001", 1610612747, "Lakers", "LAL", "LAL vs. DEN", "L", 107),
        _team_row("0022300001", 1610612743, "Nuggets", "DEN", "DEN @ LAL", "W", 119),
    ]
    games = parse_league_game_log(rows)
    assert len(games) == 1
    g = games[0]
    assert g["home_team_abbr"] == "LAL"
    assert g["away_team_abbr"] == "DEN"
    assert g["home_score"] == 107
    assert g["away_score"] == 119
    assert g["status"] == "Final"
    assert "PTS" in g["home_stats"] and "FGA" in g["away_stats"]


def test_parse_league_game_log_skips_incomplete_game():
    rows = [_team_row("0022300002", 1610612747, "Lakers", "LAL", "LAL vs. DEN", "W", 100)]
    assert parse_league_game_log(rows) == []


def test_parse_scoreboard_uses_linescore_points():
    payload = {
        "GameHeader": [
            {
                "GAME_ID": "0022300003",
                "SEASON": "2023",
                "GAME_DATE_EST": "2023-10-25T00:00:00",
                "GAME_STATUS_TEXT": "Final",
                "HOME_TEAM_ID": 1610612738,
                "VISITOR_TEAM_ID": 1610612752,
            }
        ],
        "LineScore": [
            {"GAME_ID": "0022300003", "TEAM_ID": 1610612738, "PTS": 110},
            {"GAME_ID": "0022300003", "TEAM_ID": 1610612752, "PTS": 104},
        ],
    }
    games = parse_scoreboard(payload)
    assert len(games) == 1
    assert games[0]["home_score"] == 110
    assert games[0]["away_score"] == 104
    assert games[0]["home_team_id"] == 1610612738
