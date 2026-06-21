"""Cliente async para stats.nba.com vía el paquete `nba_api`.

`nba_api` es **síncrono** (basado en `requests`); cada llamada se envuelve en
`asyncio.to_thread(...)` para no bloquear el event loop. El import de `nba_api`
es **diferido** dentro de cada método para que los tests (que mockean estas
llamadas) no requieran el paquete instalado.

Endpoints MVP:
* `league_game_log(season)` — todos los partidos de una temporada con stats por
  equipo (caballo de batalla del backfill; una sola llamada por temporada).
* `scoreboard(date_str)` — partidos de una fecha con estado y marcador.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.nba_throttle import NbaRateLimiter, get_nba_rate_limiter

# Campos de stats por equipo que conservamos (alimentan features avanzadas).
_STAT_FIELDS = (
    "PTS",
    "FGM",
    "FGA",
    "FG3M",
    "FG3A",
    "FTM",
    "FTA",
    "OREB",
    "DREB",
    "REB",
    "AST",
    "STL",
    "BLK",
    "TOV",
    "PF",
)


class NbaApiClient:
    """Cliente async para stats.nba.com (sin API key)."""

    def __init__(
        self,
        *,
        season_type: str = "Regular Season",
        timeout: float = 30.0,
        rate_limiter: NbaRateLimiter | None = None,
    ) -> None:
        self._season_type = season_type
        self._timeout = timeout
        self._limiter = rate_limiter if rate_limiter is not None else get_nba_rate_limiter()

    async def _throttle(self) -> None:
        if self._limiter is not None:
            await self._limiter.acquire()

    async def league_game_log(
        self,
        season: str,
        *,
        season_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Filas team-game de una temporada (una fila por equipo por partido)."""
        await self._throttle()
        st = season_type or self._season_type

        def _call() -> list[dict[str, Any]]:
            from nba_api.stats.endpoints import leaguegamelog

            ep = leaguegamelog.LeagueGameLog(
                season=season,
                season_type_all_star=st,
                timeout=self._timeout,
            )
            data = ep.get_normalized_dict()
            return list(data.get("LeagueGameLog", []))

        return await asyncio.to_thread(_call)

    async def scoreboard(self, date_str: str) -> dict[str, Any]:
        """Cabeceras de partidos + linescore de una fecha (YYYY-MM-DD)."""
        await self._throttle()

        def _call() -> dict[str, Any]:
            from nba_api.stats.endpoints import scoreboardv2

            ep = scoreboardv2.ScoreboardV2(game_date=date_str, timeout=self._timeout)
            return dict(ep.get_normalized_dict())

        return await asyncio.to_thread(_call)


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _stats_subset(row: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in _STAT_FIELDS:
        v = row.get(key)
        if v is None:
            continue
        try:
            out[key] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def parse_league_game_log(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa filas team-game por GAME_ID y empareja local/visitante.

    El campo MATCHUP distingue local ("LAL vs. DEN") de visitante ("LAL @ DEN").
    """
    by_game: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        gid = row.get("GAME_ID")
        if not gid:
            continue
        matchup = str(row.get("MATCHUP") or "")
        side = "away" if "@" in matchup else "home"
        by_game.setdefault(str(gid), {})[side] = row

    out: list[dict[str, Any]] = []
    for gid, sides in by_game.items():
        home = sides.get("home")
        away = sides.get("away")
        if home is None or away is None:
            continue  # partido incompleto en el log (raro); se omite
        hid = _to_int(home.get("TEAM_ID"))
        aid = _to_int(away.get("TEAM_ID"))
        if hid is None or aid is None:
            continue
        hs = _to_int(home.get("PTS"))
        aws = _to_int(away.get("PTS"))
        wl = str(home.get("WL") or "").strip().upper()
        # Estado: si hay W/L el partido está finalizado.
        status = "Final" if wl in ("W", "L") else "Scheduled"
        out.append(
            {
                "game_id": gid,
                "season": str(home.get("SEASON_ID") or ""),
                "game_date": str(home.get("GAME_DATE") or "")[:10],
                "game_datetime_utc": None,
                "status": status,
                "home_team_id": hid,
                "home_team_name": str(home.get("TEAM_NAME") or ""),
                "home_team_abbr": str(home.get("TEAM_ABBREVIATION") or ""),
                "away_team_id": aid,
                "away_team_name": str(away.get("TEAM_NAME") or ""),
                "away_team_abbr": str(away.get("TEAM_ABBREVIATION") or ""),
                "home_score": hs,
                "away_score": aws,
                "home_stats": _stats_subset(home),
                "away_stats": _stats_subset(away),
            }
        )
    return out


def parse_scoreboard(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza ScoreboardV2 (GameHeader + LineScore) a dicts de partido.

    Sin stats por equipo (el scoreboard no las trae): útil para el listado del
    día y marcadores en vivo, no para features.
    """
    headers = payload.get("GameHeader") or []
    linescores = payload.get("LineScore") or []
    pts_by_team: dict[tuple[str, int], int | None] = {}
    for ls in linescores:
        gid = str(ls.get("GAME_ID") or "")
        tid = _to_int(ls.get("TEAM_ID"))
        if not gid or tid is None:
            continue
        pts_by_team[(gid, tid)] = _to_int(ls.get("PTS"))

    out: list[dict[str, Any]] = []
    for h in headers:
        gid = str(h.get("GAME_ID") or "")
        hid = _to_int(h.get("HOME_TEAM_ID"))
        aid = _to_int(h.get("VISITOR_TEAM_ID"))
        if not gid or hid is None or aid is None:
            continue
        out.append(
            {
                "game_id": gid,
                "season": str(h.get("SEASON") or ""),
                "game_date": str(h.get("GAME_DATE_EST") or "")[:10],
                "game_datetime_utc": h.get("GAME_DATE_EST"),
                "status": str(h.get("GAME_STATUS_TEXT") or "Unknown").strip(),
                "home_team_id": hid,
                "home_team_name": "",
                "home_team_abbr": "",
                "away_team_id": aid,
                "away_team_name": "",
                "away_team_abbr": "",
                "home_score": pts_by_team.get((gid, hid)),
                "away_score": pts_by_team.get((gid, aid)),
                "home_stats": None,
                "away_stats": None,
            }
        )
    return out
