"""Integration tests for /api/v1/games/* endpoints.

Uses real DB data seeded from mock_data.py — no MagicMock.
MLB API sync calls are not triggered (sync=False or DB already has data).
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.mock_data import (
    FINAL_HOME_WIN_PK,
    SCHEDULED_GAME_PK,
)
from tests.integration.mock_data_fail import NONEXISTENT_GAME_PK

# ---------------------------------------------------------------------------
# GET /api/v1/games/{game_pk} — success cases
# ---------------------------------------------------------------------------


async def test_get_game_by_pk_returns_scheduled_game(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/games/{SCHEDULED_GAME_PK}")
    assert r.status_code == 200
    body = r.json()
    assert body["game_pk"] == SCHEDULED_GAME_PK
    assert body["status"] == "Scheduled"
    assert body["home_team"]["abbreviation"] == "LAD"
    assert body["away_team"]["abbreviation"] == "NYY"
    assert body["home_team"]["league"] == "NL"
    assert body["home_team"]["division"] == "NL West"
    assert body["away_team"]["league"] == "AL"
    assert body["away_team"]["division"] == "AL East"
    assert body["home_score"] is None
    assert body["away_score"] is None


async def test_get_final_game_has_scores(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/games/{FINAL_HOME_WIN_PK}")
    assert r.status_code == 200
    body = r.json()
    assert body["home_score"] == 7
    assert body["away_score"] == 3
    assert body["status"] == "Final"


async def test_get_game_with_predictions_includes_probability(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/games/{SCHEDULED_GAME_PK}?include_predictions=true")
    assert r.status_code == 200
    body = r.json()
    assert body.get("prediction") is not None
    pred = body["prediction"]
    assert 0.0 <= pred["home_win_probability"] <= 1.0
    assert pred["over_under_line"] > 0.0
    assert pred["model_version"] is not None


async def test_get_game_without_predictions_returns_null_prediction(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/games/{SCHEDULED_GAME_PK}?include_predictions=false")
    assert r.status_code == 200
    assert r.json().get("prediction") is None


async def test_get_game_response_includes_venue(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/games/{SCHEDULED_GAME_PK}")
    assert r.status_code == 200
    body = r.json()
    assert body["venue_name"] == "Dodger Stadium"


# ---------------------------------------------------------------------------
# GET /api/v1/games/{game_pk} — failure cases
# ---------------------------------------------------------------------------


async def test_get_game_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.get(f"/api/v1/games/{NONEXISTENT_GAME_PK}")
    assert r.status_code == 404


async def test_get_game_invalid_pk_type_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/games/not-a-number")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/games — list (no sync, just DB data)
# ---------------------------------------------------------------------------


async def test_games_list_without_sync_returns_seeded_data(client: AsyncClient) -> None:
    r = await client.get("/api/v1/games", params={"date": "2025-09-15", "sync": False, "include_predictions": False})
    assert r.status_code == 200
    body = r.json()
    assert "games" in body
    assert "meta" in body
    # The scheduled game is on 2025-09-15
    game_pks = [g["game_pk"] for g in body["games"]]
    assert SCHEDULED_GAME_PK in game_pks


async def test_detail_returns_lineups_and_boxscore(client: AsyncClient) -> None:
    """El endpoint de detalle sí debe serializar lineups/boxscore completos."""
    r = await client.get(f"/api/v1/games/{SCHEDULED_GAME_PK}")
    assert r.status_code == 200
    body = r.json()
    assert body["lineups"] == {"home": ["a", "b"], "away": ["c", "d"]}
    assert body["boxscore"] == {"teams": {"home": {}, "away": {}}}


async def test_list_defers_lineups_and_boxscore(client: AsyncClient) -> None:
    """El listado debe omitir lineups/boxscore (diferidos) para aligerar el payload."""
    r = await client.get(
        "/api/v1/games",
        params={"date": "2025-09-15", "sync": False, "include_predictions": False},
    )
    assert r.status_code == 200
    games = {g["game_pk"]: g for g in r.json()["games"]}
    assert SCHEDULED_GAME_PK in games
    assert games[SCHEDULED_GAME_PK]["lineups"] is None
    assert games[SCHEDULED_GAME_PK]["boxscore"] is None


async def test_games_list_missing_date_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/games")
    assert r.status_code == 422


async def test_games_list_invalid_date_returns_422(client: AsyncClient) -> None:
    r = await client.get("/api/v1/games", params={"date": "not-a-date"})
    assert r.status_code == 422
