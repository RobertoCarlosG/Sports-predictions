from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.mlb import Game, Team
from app.data.mlb_team_abbreviations import team_abbr_for_display
from app.services.mlb_client import (
    MlbApiClient,
    parse_schedule_games,
    scores_from_linescore_payload,
)

# Mínimo por sentencia al escribir `boxscore_json` (payload MLB ~10²–10³ KB) o bajo contención.
_MLB_TX_STATEMENT_TIMEOUT_MIN_S = 300


def _mlb_write_statement_timeout_seconds() -> int:
    b = settings.database_statement_timeout_seconds
    if b <= 0:
        return _MLB_TX_STATEMENT_TIMEOUT_MIN_S
    return max(b, _MLB_TX_STATEMENT_TIMEOUT_MIN_S)


async def _set_local_statement_timeout_for_mlb_write(session: AsyncSession) -> None:
    """Evita `QueryCanceled` en UPDATE con JSON grande o espera a locks, sin subir el límite global de todo el proceso."""
    sec = _mlb_write_statement_timeout_seconds()
    await session.execute(text(f"SET LOCAL statement_timeout = '{sec}s'"))


def _scores_from_boxscore(box: dict[str, Any]) -> tuple[int | None, int | None]:
    try:
        hr = int(box["teams"]["home"]["teamStats"]["batting"]["runs"])
        ar = int(box["teams"]["away"]["teamStats"]["batting"]["runs"])
        return hr, ar
    except (KeyError, TypeError, ValueError):
        return None, None


def lineups_from_boxscore(box: dict[str, Any]) -> dict[str, Any] | None:
    """Alineación / orden de bateo desde boxscore.

    El endpoint `/game/{pk}/feed/live` suele devolver **404** en partidos ya finalizados;
    el boxscore sí incluye `batters`, `players` y `battingOrder`.
    """
    teams = box.get("teams")
    if not isinstance(teams, dict):
        return None
    out: dict[str, Any] = {"source": "boxscore"}
    any_rows = False
    for side in ("away", "home"):
        t = teams.get(side)
        if not isinstance(t, dict):
            continue
        team_info = t.get("team")
        team_info = team_info if isinstance(team_info, dict) else {}
        label = str(
            team_info.get("abbreviation")
            or team_info.get("teamName")
            or team_info.get("name")
            or side
        )
        players = t.get("players")
        if not isinstance(players, dict):
            players = {}
        ids = t.get("batters")
        if not isinstance(ids, list):
            ids = t.get("battingOrder") or []
        if not isinstance(ids, list):
            ids = []
        rows: list[dict[str, Any]] = []
        for pid in ids:
            key = f"ID{pid}"
            p = players.get(key)
            if not isinstance(p, dict):
                rows.append({"playerId": pid})
                continue
            person = p.get("person")
            person = person if isinstance(person, dict) else {}
            pos = p.get("position")
            pos = pos if isinstance(pos, dict) else {}
            rows.append(
                {
                    "playerId": pid,
                    "name": person.get("fullName"),
                    "position": pos.get("abbreviation") or pos.get("name"),
                    "jersey": p.get("jerseyNumber"),
                    "battingOrder": p.get("battingOrder"),
                }
            )
        if rows:
            any_rows = True
        out[side] = {"team": label, "batters": rows}
    if not any_rows:
        return None
    return out


async def upsert_team(
    session: AsyncSession,
    team_id: int,
    name: str,
    abbreviation: str,
    venue_id: int | None,
    venue_name: str | None,
) -> Team:
    result = await session.execute(select(Team).where(Team.id == team_id))
    row = result.scalar_one_or_none()
    if row is None:
        row = Team(
            id=team_id,
            name=name,
            abbreviation=abbreviation[:8],
            venue_id=venue_id,
            venue_name=venue_name,
        )
        session.add(row)
    else:
        row.name = name
        row.abbreviation = abbreviation[:8]
        row.venue_id = venue_id
        row.venue_name = venue_name
    return row


async def _upsert_game_from_schedule_item(
    session: AsyncSession,
    client: MlbApiClient,
    item: dict[str, Any],
    *,
    fetch_details: bool,
) -> Game:
    hid = item.get("home_team_id")
    aid = item.get("away_team_id")
    if hid is None or aid is None:
        raise ValueError("schedule item missing team ids")
    home_name = str(item.get("home_team_name") or "Home")
    away_name = str(item.get("away_team_name") or "Away")
    h_abbr = team_abbr_for_display(
        int(hid), str(item.get("home_team_abbr") or ""), home_name
    )
    a_abbr = team_abbr_for_display(
        int(aid), str(item.get("away_team_abbr") or ""), away_name
    )
    # Orden fijo por id evita deadlocks entre peticiones concurrentes que tocaban
    # home/away en distinto orden (mismas filas en `teams`, distinto orden de locks).
    venue_id = item.get("venue_id")
    venue_name = item.get("venue_name")
    for tid, name, abbr in sorted(
        [
            (int(hid), home_name, h_abbr),
            (int(aid), away_name, a_abbr),
        ],
        key=lambda t: t[0],
    ):
        await upsert_team(session, tid, name, abbr, venue_id, venue_name)

    gd = dt.date.fromisoformat(str(item["game_date"]))
    gdt: dt.datetime | None = None
    if item.get("game_datetime_utc"):
        try:
            raw_dt = str(item["game_datetime_utc"]).replace("Z", "+00:00")
            gdt = dt.datetime.fromisoformat(raw_dt)
        except ValueError:
            gdt = None

    result = await session.execute(select(Game).where(Game.game_pk == item["game_pk"]))
    game = result.scalar_one_or_none()
    lineups_json: dict[str, Any] | None = None
    boxscore_json: dict[str, Any] | None = None

    if fetch_details:
        try:
            boxscore_json = await client.boxscore(item["game_pk"])
        except Exception:
            boxscore_json = None
        lineups_json = None
        try:
            live = await client.live_feed(item["game_pk"])
            lineups_json = {"liveFeed": live}
        except Exception:
            pass
        if lineups_json is None and boxscore_json is not None:
            extracted = lineups_from_boxscore(boxscore_json)
            if extracted is not None:
                lineups_json = extracted

    hs = item.get("home_score")
    aws = item.get("away_score")
    home_score = int(hs) if hs is not None else None
    away_score = int(aws) if aws is not None else None
    if (home_score is None or away_score is None) and boxscore_json:
        bh, ba = _scores_from_boxscore(boxscore_json)
        if home_score is None:
            home_score = bh
        if away_score is None:
            away_score = ba
    if home_score is None or away_score is None:
        try:
            ls = await client.linescore(item["game_pk"])
            lh, la = scores_from_linescore_payload(ls)
            if home_score is None:
                home_score = lh
            if away_score is None:
                away_score = la
        except Exception:
            pass

    if game is None:
        game = Game(
            game_pk=item["game_pk"],
            season=item.get("season") or str(gd.year),
            game_date=gd,
            game_datetime_utc=gdt,
            status=str(item.get("status") or "Unknown"),
            home_team_id=int(hid),
            away_team_id=int(aid),
            venue_id=item.get("venue_id"),
            venue_name=item.get("venue_name"),
            home_score=home_score,
            away_score=away_score,
            lineups_json=lineups_json,
            boxscore_json=boxscore_json,
        )
        session.add(game)
    else:
        game.status = str(item.get("status") or game.status)
        game.game_datetime_utc = gdt or game.game_datetime_utc
        game.venue_id = item.get("venue_id")
        game.venue_name = item.get("venue_name")
        if home_score is not None:
            game.home_score = home_score
        if away_score is not None:
            game.away_score = away_score
        if lineups_json is not None:
            game.lineups_json = lineups_json
        if boxscore_json is not None:
            game.boxscore_json = boxscore_json

    await session.flush()
    return game


async def sync_games_for_date(
    session: AsyncSession,
    client: MlbApiClient,
    date_str: str,
    *,
    fetch_details: bool = True,
) -> list[Game]:
    """Fetch MLB schedule for a date, upsert teams/games, optionally boxscore + live lineups."""
    await _set_local_statement_timeout_for_mlb_write(session)
    raw = await client.schedule(date_str)
    parsed = parse_schedule_games(raw)
    games: list[Game] = []
    for item in parsed:
        hid = item.get("home_team_id")
        aid = item.get("away_team_id")
        if hid is None or aid is None:
            continue
        g = await _upsert_game_from_schedule_item(
            session, client, item, fetch_details=fetch_details
        )
        games.append(g)
    return games


async def sync_single_game(
    session: AsyncSession,
    client: MlbApiClient,
    game_pk: int,
    *,
    fetch_details: bool = True,
) -> Game | None:
    """Upsert un partido por `game_pk` usando el schedule de MLB (sin recorrer todo el día)."""
    await _set_local_statement_timeout_for_mlb_write(session)
    raw = await client.schedule_for_game(game_pk)
    parsed = parse_schedule_games(raw)
    item = next((x for x in parsed if x["game_pk"] == game_pk), None)
    if item is None:
        return None
    return await _upsert_game_from_schedule_item(
        session, client, item, fetch_details=fetch_details
    )
