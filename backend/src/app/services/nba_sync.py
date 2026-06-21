"""Sincronización de partidos NBA (espeja mlb_sync.py, más simple).

Sin lineups ni pitchers: NBA solo necesita partidos, equipos y stats por equipo.
`sync_season` (vía leaguegamelog) es el entry point del backfill.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.nba_team_meta import nba_abbr_for_display, nba_meta_for
from app.models.nba import NbaGame, NbaTeam
from app.services.nba_client import (
    NbaApiClient,
    parse_league_game_log,
    parse_scoreboard,
)


async def upsert_nba_team(
    session: AsyncSession,
    team_id: int,
    name: str,
    abbreviation: str,
) -> NbaTeam:
    meta = nba_meta_for(team_id)
    conference = meta[1] if meta is not None else None
    division = meta[2] if meta is not None else None
    abbr = (abbreviation or nba_abbr_for_display(team_id))[:8]

    result = await session.execute(select(NbaTeam).where(NbaTeam.id == team_id))
    row = result.scalar_one_or_none()
    if row is None:
        row = NbaTeam(
            id=team_id,
            name=name or abbr,
            abbreviation=abbr,
            conference=conference,
            division=division,
        )
        session.add(row)
    else:
        needs_update = False
        if name and row.name != name:
            row.name = name
            needs_update = True
        if abbr and row.abbreviation != abbr:
            row.abbreviation = abbr
            needs_update = True
        if conference is not None and row.conference != conference:
            row.conference = conference
            needs_update = True
        if division is not None and row.division != division:
            row.division = division
            needs_update = True
        if not needs_update:
            session.expire(row)
    return row


def _parse_game_date(value: str) -> dt.date | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw[:10])
    except ValueError:
        return None


async def _upsert_game(
    session: AsyncSession,
    item: dict[str, Any],
    *,
    flush: bool = True,
    skip_team_upsert: bool = False,
) -> NbaGame | None:
    hid = item.get("home_team_id")
    aid = item.get("away_team_id")
    gid = item.get("game_id")
    if hid is None or aid is None or not gid:
        return None
    gd = _parse_game_date(str(item.get("game_date") or ""))
    if gd is None:
        return None

    if not skip_team_upsert:
        await upsert_nba_team(
            session,
            int(hid),
            str(item.get("home_team_name") or ""),
            str(item.get("home_team_abbr") or ""),
        )
        await upsert_nba_team(
            session,
            int(aid),
            str(item.get("away_team_name") or ""),
            str(item.get("away_team_abbr") or ""),
        )
        if flush:
            await session.flush()

    home_stats = item.get("home_stats")
    away_stats = item.get("away_stats")
    boxscore_json: dict[str, Any] | None = None
    if home_stats or away_stats:
        boxscore_json = {"home": home_stats or {}, "away": away_stats or {}}

    hs = item.get("home_score")
    aws = item.get("away_score")
    home_score = int(hs) if hs is not None else None
    away_score = int(aws) if aws is not None else None

    result = await session.execute(select(NbaGame).where(NbaGame.game_id == str(gid)))
    game = result.scalar_one_or_none()
    if game is None:
        game = NbaGame(
            game_id=str(gid),
            season=str(item.get("season") or str(gd.year)),
            game_date=gd,
            game_datetime_utc=None,
            status=str(item.get("status") or "Unknown"),
            home_team_id=int(hid),
            away_team_id=int(aid),
            arena=item.get("arena"),
            home_score=home_score,
            away_score=away_score,
            boxscore_json=boxscore_json,
        )
        session.add(game)
    else:
        game.status = str(item.get("status") or game.status)
        if home_score is not None:
            game.home_score = home_score
        if away_score is not None:
            game.away_score = away_score
        if boxscore_json is not None:
            game.boxscore_json = boxscore_json
    if flush:
        await session.flush()
    return game


async def upsert_parsed_games(
    session: AsyncSession,
    parsed: list[dict[str, Any]],
    season: str | None = None,
    *,
    chunk_size: int = 100,
) -> list[NbaGame]:
    """Inserta/actualiza partidos a partir de items ya parseados (sin red).

    Separado de sync_season para poder hacer el fetch de la API ANTES de abrir
    la sesión DB y evitar que un statement_timeout cancele el INSERT mientras
    la red está activa.

    Estrategia de batching para minimizar round-trips al DB:
    1. Pre-upsert los ≤30 equipos únicos → 1 flush.
    2. Upsert juegos en chunks de `chunk_size` → flush cada chunk.
    Reduce ~2450 flushes (para 1225 juegos) a ~13.
    """
    # 1. Pre-upsert todos los equipos únicos en un solo flush.
    seen_team_ids: set[int] = set()
    for item in parsed:
        for tid_key, name_key, abbr_key in (
            ("home_team_id", "home_team_name", "home_team_abbr"),
            ("away_team_id", "away_team_name", "away_team_abbr"),
        ):
            raw_tid = item.get(tid_key)
            if raw_tid is None:
                continue
            tid = int(raw_tid)
            if tid in seen_team_ids:
                continue
            seen_team_ids.add(tid)
            await upsert_nba_team(
                session,
                tid,
                str(item.get(name_key) or ""),
                str(item.get(abbr_key) or ""),
            )
    await session.flush()

    # 2. Upsert juegos en chunks; skip_team_upsert=True porque ya están en DB.
    games: list[NbaGame] = []
    for idx, item in enumerate(parsed):
        if season is not None and not item.get("season"):
            item = {**item, "season": season}
        g = await _upsert_game(session, item, flush=False, skip_team_upsert=True)
        if g is not None:
            games.append(g)
        if (idx + 1) % chunk_size == 0:
            await session.flush()
    await session.flush()
    return games


async def sync_season(
    session: AsyncSession,
    client: NbaApiClient,
    season: str,
    *,
    season_type: str | None = None,
) -> list[NbaGame]:
    """Backfill de una temporada completa vía leaguegamelog (una sola llamada)."""
    rows = await client.league_game_log(season, season_type=season_type)
    parsed = parse_league_game_log(rows)
    return await upsert_parsed_games(session, parsed, season)


async def sync_games_for_date(
    session: AsyncSession,
    client: NbaApiClient,
    date_str: str,
) -> list[NbaGame]:
    """Sincroniza partidos de una fecha vía scoreboard (sin stats por equipo)."""
    raw = await client.scoreboard(date_str)
    parsed = parse_scoreboard(raw)
    games: list[NbaGame] = []
    for item in parsed:
        # El scoreboard no trae nombres/abreviaturas; el mapa estático los rellena.
        item.setdefault("home_team_name", "")
        item.setdefault("away_team_name", "")
        item["home_team_abbr"] = nba_abbr_for_display(item.get("home_team_id"))
        item["away_team_abbr"] = nba_abbr_for_display(item.get("away_team_id"))
        g = await _upsert_game(session, item)
        if g is not None:
            games.append(g)
    return games
