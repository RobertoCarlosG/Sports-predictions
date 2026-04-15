from __future__ import annotations

from typing import Any, cast

import httpx


class MlbApiClient:
    """Async client for statsapi.mlb.com (no API key)."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip("/")
        self._client = client

    async def schedule(self, date_str: str, sport_id: int = 1) -> dict[str, Any]:
        r = await self._client.get(
            f"{self._base}/schedule",
            params={"sportId": sport_id, "date": date_str},
        )
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def boxscore(self, game_pk: int) -> dict[str, Any]:
        r = await self._client.get(f"{self._base}/game/{game_pk}/boxscore")
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def live_feed(self, game_pk: int) -> dict[str, Any]:
        r = await self._client.get(f"{self._base}/game/{game_pk}/feed/live")
        r.raise_for_status()
        return cast(dict[str, Any], r.json())


def parse_schedule_games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize schedule JSON into a list of dicts with keys we persist."""
    out: list[dict[str, Any]] = []
    for day in payload.get("dates", []):
        for g in day.get("games", []):
            teams = g.get("teams", {})
            home = teams.get("home", {}).get("team", {})
            away = teams.get("away", {}).get("team", {})
            venue = g.get("venue", {})
            status = g.get("status", {})
            detailed = status.get("detailedState") or status.get("abstractGameState") or "Unknown"
            game_date = day.get("date") or (g.get("gameDate") or "")[:10]
            out.append(
                {
                    "game_pk": g["gamePk"],
                    "season": str(g.get("season", "")),
                    "game_date": game_date,
                    "game_datetime_utc": g.get("gameDate"),
                    "status": detailed,
                    "home_team_id": home.get("id"),
                    "home_team_name": home.get("name", ""),
                    "home_team_abbr": home.get("abbreviation") or home.get("teamName", "HOME")[:8],
                    "away_team_id": away.get("id"),
                    "away_team_name": away.get("name", ""),
                    "away_team_abbr": away.get("abbreviation") or away.get("teamName", "AWAY")[:8],
                    "venue_id": venue.get("id"),
                    "venue_name": venue.get("name"),
                }
            )
    return out
