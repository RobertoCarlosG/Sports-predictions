"""Integration tests for /api/v1/mlb/* endpoints.

Sync endpoints (POST) require MLB API access — those tests skip gracefully
if the network is unavailable. Read endpoints (GET) use seeded DB data.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.mock_data import FINAL_HOME_WIN_PK
from tests.integration.mock_data_fail import (
    MLB_SYNC_END_BEFORE_START,
    MLB_SYNC_INVALID_DATE,
    MLB_SYNC_MISSING_END,
    MLB_SYNC_MISSING_START,
    NONEXISTENT_GAME_PK,
)

# ---------------------------------------------------------------------------
# GET /api/v1/mlb/teams
# ---------------------------------------------------------------------------


async def test_get_teams_returns_seeded_teams(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/teams")
    assert r.status_code == 200
    teams = r.json()
    assert isinstance(teams, list)
    abbrs = [t["abbreviation"] for t in teams]
    assert "LAD" in abbrs
    assert "NYY" in abbrs
    assert "BOS" in abbrs


async def test_get_teams_structure(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/teams")
    assert r.status_code == 200
    for team in r.json():
        assert "id" in team
        assert "name" in team
        assert "abbreviation" in team


# ---------------------------------------------------------------------------
# GET /api/v1/mlb/history/games
# ---------------------------------------------------------------------------


async def test_history_games_returns_seeded_games(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/history/games", params={"season": "2025"})
    assert r.status_code == 200
    games = r.json()
    assert isinstance(games, list)
    assert len(games) >= 2  # at least final home win + final away win


async def test_history_games_only_final_filter(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/history/games", params={"season": "2025", "only_final": True})
    assert r.status_code == 200
    games = r.json()
    for g in games:
        assert "Final" in g["status"] or g["status"] == "Final"


async def test_history_games_limit_and_offset(client: AsyncClient) -> None:
    r1 = await client.get("/api/v1/mlb/history/games", params={"limit": 2, "offset": 0})
    r2 = await client.get("/api/v1/mlb/history/games", params={"limit": 2, "offset": 2})
    assert r1.status_code == 200
    assert r2.status_code == 200
    pks1 = {g["game_pk"] for g in r1.json()}
    pks2 = {g["game_pk"] for g in r2.json()}
    # With offset they should differ (if enough data)
    assert pks1 != pks2 or len(pks1) == 0


async def test_history_games_limit_too_high_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/history/games", params={"limit": 501})
    assert r.status_code == 422


async def test_history_games_limit_zero_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/history/games", params={"limit": 0})
    assert r.status_code == 422


async def test_history_games_negative_offset_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/history/games", params={"offset": -1})
    assert r.status_code == 422


async def test_history_games_by_team_filter(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/history/games", params={"team_id": 119})  # LAD
    assert r.status_code == 200
    # All returned games should involve LAD (team_id=119)
    for g in r.json():
        team_ids = {g["home_team"]["id"], g["away_team"]["id"]}
        assert 119 in team_ids


# ---------------------------------------------------------------------------
# GET /api/v1/mlb/history/games/{game_pk}
# ---------------------------------------------------------------------------


async def test_history_game_by_pk_returns_game(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/mlb/history/games/{FINAL_HOME_WIN_PK}")
    assert r.status_code == 200
    body = r.json()
    assert body["game_pk"] == FINAL_HOME_WIN_PK
    assert body["sport_code"] == "mlb"
    assert body["home_score"] == 7
    assert body["away_score"] == 3


async def test_history_game_by_pk_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/mlb/history/games/{NONEXISTENT_GAME_PK}")
    assert r.status_code == 404


async def test_history_game_invalid_pk_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/mlb/history/games/not-a-number")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/mlb/sync-range — validation failure cases (no network needed)
# ---------------------------------------------------------------------------


async def test_sync_range_end_before_start_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/v1/mlb/sync-range", json=MLB_SYNC_END_BEFORE_START)
    assert r.status_code == 422


async def test_sync_range_missing_start_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/v1/mlb/sync-range", json=MLB_SYNC_MISSING_START)
    assert r.status_code == 422


async def test_sync_range_missing_end_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/v1/mlb/sync-range", json=MLB_SYNC_MISSING_END)
    assert r.status_code == 422


async def test_sync_range_invalid_date_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/v1/mlb/sync-range", json=MLB_SYNC_INVALID_DATE)
    assert r.status_code == 422
