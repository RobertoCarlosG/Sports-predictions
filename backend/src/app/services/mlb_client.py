from __future__ import annotations

from typing import Any, cast

import httpx

from app.data.mlb_team_abbreviations import team_abbr_for_display
from app.services.mlb_throttle import MlbRateLimiter, get_mlb_rate_limiter


class MlbApiClient:
    """Async client for statsapi.mlb.com (no API key)."""

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        *,
        rate_limiter: MlbRateLimiter | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._client = client
        self._limiter = rate_limiter if rate_limiter is not None else get_mlb_rate_limiter()

    async def _throttle(self) -> None:
        if self._limiter is not None:
            await self._limiter.acquire()

    async def schedule(self, date_str: str, sport_id: int = 1) -> dict[str, Any]:
        # Without hydrate=team, each team is only id/name/link; hydrate=team adds
        # abbreviation, teamName, fileCode, etc. (MLB Stats API schedule).
        await self._throttle()
        r = await self._client.get(
            f"{self._base}/schedule",
            params={
                "sportId": sport_id,
                "date": date_str,
                "hydrate": "team,probablePitcher",
            },
        )
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def schedule_for_game(self, game_pk: int, sport_id: int = 1) -> dict[str, Any]:
        """Schedule filtrado por un solo `gamePk` (útil para sync puntual sin iterar el día)."""
        await self._throttle()
        r = await self._client.get(
            f"{self._base}/schedule",
            params={
                "sportId": sport_id,
                "gamePk": game_pk,
                "hydrate": "team,probablePitcher",
            },
        )
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def boxscore(self, game_pk: int) -> dict[str, Any]:
        await self._throttle()
        r = await self._client.get(f"{self._base}/game/{game_pk}/boxscore")
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def live_feed(self, game_pk: int) -> dict[str, Any]:
        await self._throttle()
        r = await self._client.get(f"{self._base}/game/{game_pk}/feed/live")
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def linescore(self, game_pk: int) -> dict[str, Any]:
        """Ligero; incluye runs por equipo (útil si el schedule no trae score y no hay boxscore)."""
        await self._throttle()
        r = await self._client.get(f"{self._base}/game/{game_pk}/linescore")
        r.raise_for_status()
        return cast(dict[str, Any], r.json())

    async def team_season_pitching_era(self, team_id: int, season: str) -> float | None:
        """ERA colectivo de pitcheo del equipo (rotación + bullpen) vía /teams/{id}/stats."""
        await self._throttle()
        r = await self._client.get(
            f"{self._base}/teams/{team_id}/stats",
            params={"season": season, "group": "pitching", "stats": "season", "sportIds": 1},
        )
        r.raise_for_status()
        return _era_from_season_stats_payload(r.json())

    async def person_season_pitching_era(self, person_id: int, season: str) -> float | None:
        """ERA de temporada (pitching) de un jugador vía /people/{id}/stats."""
        await self._throttle()
        r = await self._client.get(
            f"{self._base}/people/{person_id}/stats",
            params={"stats": "season", "season": season, "group": "pitching", "sportIds": 1},
        )
        r.raise_for_status()
        return _era_from_season_stats_payload(r.json())


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


def _era_from_season_stats_payload(payload: dict[str, Any]) -> float | None:
    """Extrae ERA del primer split de /teams/.../stats o /people/.../stats (temporada, pitching)."""
    try:
        stats = payload.get("stats")
        if not isinstance(stats, list) or not stats:
            return None
        splits = stats[0].get("splits")
        if not isinstance(splits, list) or not splits:
            return None
        st = splits[0].get("stat")
        if not isinstance(st, dict):
            return None
        raw = st.get("era")
        if raw is None:
            return None
        return float(str(raw).strip().replace(",", ""))
    except (TypeError, ValueError, KeyError, IndexError):
        return None


def team_abbreviation(team: dict[str, Any]) -> str:
    """Short label for UI; hydrate=team + mapa por id evita HOME/AWAY con PgBouncer/API parcial."""
    tid = team.get("id")
    try:
        t_id = int(tid) if tid is not None else 0
    except (TypeError, ValueError):
        t_id = 0
    raw = _raw_abbr_from_team_payload(team)
    return team_abbr_for_display(t_id, raw, str(team.get("name", "")))


def _probable_pitcher_id(side: dict[str, Any]) -> int | None:
    p = side.get("probablePitcher")
    if not isinstance(p, dict):
        return None
    pid = p.get("id")
    try:
        return int(pid) if pid is not None else None
    except (TypeError, ValueError):
        return None


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
                    "home_starter_id": _probable_pitcher_id(home_side),
                    "away_team_id": away.get("id"),
                    "away_team_name": away.get("name", ""),
                    "away_team_abbr": team_abbreviation(away),
                    "away_starter_id": _probable_pitcher_id(away_side),
                    "home_score": hs,
                    "away_score": aws,
                    "venue_id": venue.get("id"),
                    "venue_name": venue.get("name"),
                }
            )
    return out
