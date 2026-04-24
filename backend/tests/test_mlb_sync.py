from app.services.mlb_sync import lineups_from_boxscore, starters_from_boxscore


def test_lineups_from_boxscore_extracts_batters() -> None:
    box = {
        "teams": {
            "away": {
                "team": {"abbreviation": "AWY", "name": "Away Club"},
                "players": {
                    "ID111": {
                        "person": {"fullName": "Uno Away"},
                        "position": {"abbreviation": "CF"},
                        "jerseyNumber": "1",
                        "battingOrder": "101",
                    }
                },
                "batters": [111],
            },
            "home": {
                "team": {"abbreviation": "HOM"},
                "players": {
                    "ID222": {
                        "person": {"fullName": "Dos Home"},
                        "position": {"abbreviation": "2B"},
                    }
                },
                "batters": [222],
            },
        }
    }
    out = lineups_from_boxscore(box)
    assert out is not None
    assert out["source"] == "boxscore"
    assert out["away"]["team"] == "AWY"
    assert len(out["away"]["batters"]) == 1
    assert out["away"]["batters"][0]["name"] == "Uno Away"
    assert out["home"]["batters"][0]["name"] == "Dos Home"


def test_lineups_from_boxscore_returns_none_without_teams() -> None:
    assert lineups_from_boxscore({}) is None
    assert lineups_from_boxscore({"teams": {}}) is None


def test_starters_from_boxscore_first_pitchers() -> None:
    box = {
        "teams": {
            "home": {"pitchers": [123, 456]},
            "away": {"pitchers": [999]},
        }
    }
    h, a = starters_from_boxscore(box)
    assert h == 123
    assert a == 999


def test_starters_from_boxscore_empty() -> None:
    assert starters_from_boxscore({}) == (None, None)
    assert starters_from_boxscore({"teams": {"home": {}, "away": {}}}) == (None, None)
