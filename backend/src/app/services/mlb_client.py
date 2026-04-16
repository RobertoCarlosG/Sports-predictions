from __future__ import annotations

from typing import Any, cast

import httpx

from app.data.mlb_team_abbreviations import team_abbr_for_display


class MlbApiClient:
    """Async client for statsapi.mlb.com (no API key)."""

    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip("/")
        self._client = client

    async def schedule(self, date_str: str, sport_id: int = 1) -> dict[str, Any]:
        # Without hydrate=team, each team is only id/name/link; hydrate=team adds
        # abbreviation, teamName, fileCode, etc. (MLB Stats API schedule).
        r = await self._client.get(
            f"{self._base}/schedule",
            params={
                "sportId": sport_id,
                "date": date_str,
                "hydrate": "team",
            },
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

    async def linescore(self, game_pk: int) -> dict[str, Any]:
        """Ligero; incluye runs por equipo (útil si el schedule no trae score y no hay boxscore)."""
        r = await self._client.get(f"{self._base}/game/{game_pk}/linescore")
        r.raise_for_status()
        return cast(dict[str, Any], r.json())


def scores_from_linescore_payload(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """Runs totales: home_score, away_score."""
    teams = payload.get("teams") or {}
    hs = _optional_int_score((teams.get("home") or {}).get("runs"))
    aws = _optional_int_score((teams.get("away") or {}).get("runs"))
    return hs, aws


def _optional_int_score(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _raw_abbr_from_team_payload(team: dict[str, Any]) -> str:
    abbr = team.get("abbreviation")
    if isinstance(abbr, str) and abbr.strip():
        return abbr.strip().upper()[:8]
    fc = team.get("fileCode")
    if isinstance(fc, str) and fc.strip():
        return fc.strip().upper()[:8]
    tn = team.get("teamName")
    if isinstance(tn, str) and tn.strip():
        return tn.strip()[:8].upper()
    name = team.get("name")
    if isinstance(name, str) and name.strip():
        parts = name.split()
        if parts:
            return parts[-1][:8].upper()
    return "?"


def team_abbreviation(team: dict[str, Any]) -> str:
    """Short label for UI; hydrate=team + mapa por id evita HOME/AWAY con PgBouncer/API parcial."""
    tid = team.get("id")
    try:
        t_id = int(tid) if tid is not None else 0
    except (TypeError, ValueError):
        t_id = 0
    raw = _raw_abbr_from_team_payload(team)
    return team_abbr_for_display(t_id, raw, str(team.get("name", "")))


def parse_schedule_games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize schedule JSON into a list of dicts with keys we persist."""
    out: list[dict[str, Any]] = []
    for day in payload.get("dates", []):
        for g in day.get("games", []):
            teams = g.get("teams", {})
            home_side = teams.get("home", {})
            away_side = teams.get("away", {})
            home = home_side.get("team", {})
            away = away_side.get("team", {})
            venue = g.get("venue", {})
            status = g.get("status", {})
            detailed = status.get("detailedState") or status.get("abstractGameState") or "Unknown"
            game_date = day.get("date") or (g.get("gameDate") or "")[:10]
            hs = _optional_int_score(home_side.get("score"))
            aws = _optional_int_score(away_side.get("score"))
            out.append(
                {
                    "game_pk": g["gamePk"],
                    "season": str(g.get("season", "")),
                    "game_date": game_date,
                    "game_datetime_utc": g.get("gameDate"),
                    "status": detailed,
                    "home_team_id": home.get("id"),
                    "home_team_name": home.get("name", ""),
                    "home_team_abbr": team_abbreviation(home),
                    "away_team_id": away.get("id"),
                    "away_team_name": away.get("name", ""),
                    "away_team_abbr": team_abbreviation(away),
                    "home_score": hs,
                    "away_score": aws,
                    "venue_id": venue.get("id"),
                    "venue_name": venue.get("name"),
                }
            )
    return out
