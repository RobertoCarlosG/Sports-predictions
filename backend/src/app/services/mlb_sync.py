from __future__ import annotations

import asyncio
import datetime as dt
import json
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


def _is_final_schedule_status(status: str) -> bool:
    s = (status or "").lower()
    return any(x in s for x in ("final", "completed", "game over"))


def _json_repr_for_compare(obj: object | None) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, sort_keys=True, default=str)


def starters_from_boxscore(box: dict[str, Any]) -> tuple[int | None, int | None]:
    """Abridores: el primer `pitchers[]` en el box de MLB (partido finalizado o avanzado)."""
    teams = box.get("teams")
    if not isinstance(teams, dict):
        return None, None

    def _first_pitcher(side: str) -> int | None:
        t = teams.get(side) or {}
        if not isinstance(t, dict):
            t = {}
        plist = t.get("pitchers")
        if not isinstance(plist, list) or len(plist) < 1:
            return None
        try:
            return int(plist[0])
        except (TypeError, ValueError):
            return None

    return _first_pitcher("home"), _first_pitcher("away")


def _int_or_none(x: object) -> int | None:
    if x is None:
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


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


def _home_away_team_specs(
    item: dict[str, Any],
) -> list[tuple[int, str, str, int | None, str | None]]:
    """Pares (team_id, …) del partido, ordenados por id (misma convención que en upsert de juego)."""
    hid = item.get("home_team_id")
    aid = item.get("away_team_id")
    if hid is None or aid is None:
        return []
    home_name = str(item.get("home_team_name") or "Home")
    away_name = str(item.get("away_team_name") or "Away")
    h_abbr = team_abbr_for_display(
        int(hid), str(item.get("home_team_abbr") or ""), home_name
    )
    a_abbr = team_abbr_for_display(
        int(aid), str(item.get("away_team_abbr") or ""), away_name
    )
    venue_id = item.get("venue_id")
    venue_name = item.get("venue_name")
    specs = [
        (int(hid), home_name, h_abbr, venue_id, venue_name),
        (int(aid), away_name, a_abbr, venue_id, venue_name),
    ]
    specs.sort(key=lambda t: t[0])
    return specs


async def _upsert_teams_for_full_schedule(
    session: AsyncSession,
    parsed: list[dict[str, Any]],
) -> None:
    """
    Bloquea/actualiza filas de `teams` una sola vez en orden global por id.

    Evita deadlocks cuando varias fechas se sincronizan en paralelo: dentro de una
    transacción, recorrer partidos en orden del calendario implica un orden de ids
    distinto al de otra transacción (p. ej. 146→138 vs 138→146).
    """
    merged: dict[int, tuple[str, str, int | None, str | None]] = {}
    for item in parsed:
        for tid, name, abbr, vid, vname in _home_away_team_specs(item):
            merged[tid] = (name, abbr, vid, vname)
    for tid in sorted(merged):
        name, abbr, vid, vname = merged[tid]
        await upsert_team(session, tid, name, abbr, vid, vname)
    await session.flush()


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
        # Solo actualizar si hay cambios reales (reduce contención de locks)
        needs_update = False
        if row.name != name:
            row.name = name
            needs_update = True
        abbr_short = abbreviation[:8]
        if row.abbreviation != abbr_short:
            row.abbreviation = abbr_short
            needs_update = True
        if row.venue_id != venue_id:
            row.venue_id = venue_id
            needs_update = True
        if row.venue_name != venue_name:
            row.venue_name = venue_name
            needs_update = True
        
        # Si no hay cambios, marcar como "sin cambios" para SQLAlchemy
        if not needs_update:
            session.expire(row)
    return row


async def _upsert_game_from_schedule_item(
    session: AsyncSession,
    client: MlbApiClient,
    item: dict[str, Any],
    *,
    fetch_details: bool,
    skip_team_upsert: bool = False,
    prefetched_boxscore: dict[str, Any] | None = None,
    prefetched_live_feed: dict[str, Any] | None = None,
    prefetched_linescore: dict[str, Any] | None = None,
) -> Game:
    hid = item.get("home_team_id")
    aid = item.get("away_team_id")
    if hid is None or aid is None:
        raise ValueError("schedule item missing team ids")
    if not skip_team_upsert:
        await _set_local_statement_timeout_for_mlb_write(session)
        for tid, name, abbr, vid, vname in _home_away_team_specs(item):
            await upsert_team(session, tid, name, abbr, vid, vname)
        await session.flush()

    gd = dt.date.fromisoformat(str(item["game_date"]))
    gdt: dt.datetime | None = None
    if item.get("game_datetime_utc"):
        try:
            raw_dt = str(item["game_datetime_utc"]).replace("Z", "+00:00")
            gdt = dt.datetime.fromisoformat(raw_dt)
        except ValueError:
            gdt = None

    # 1) Solo HTTP: sin conexión a Postgres en uso (no SELECT antes). Evita "commit+SET LOCAL"
    #    en una sesión con NullPool, que en asyncpg dejaba conexión inválida.
    lineups_json: dict[str, Any] | None = None
    boxscore_json: dict[str, Any] | None = None

    if fetch_details:
        if prefetched_boxscore is not None:
            boxscore_json = prefetched_boxscore
        else:
            try:
                boxscore_json = await client.boxscore(item["game_pk"])
            except Exception:
                boxscore_json = None
                
        lineups_json = None
        if prefetched_live_feed is not None:
            lineups_json = {"liveFeed": prefetched_live_feed}
        elif not _is_final_schedule_status(str(item.get("status") or "")):
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
            ls = prefetched_linescore if prefetched_linescore is not None else await client.linescore(item["game_pk"])
            lh, la = scores_from_linescore_payload(ls)
            if home_score is None:
                home_score = lh
            if away_score is None:
                away_score = la
        except Exception:
            pass

    home_starter = _int_or_none(item.get("home_starter_id"))
    away_starter = _int_or_none(item.get("away_starter_id"))
    if boxscore_json is not None:
        sp_h, sp_a = starters_from_boxscore(boxscore_json)
        if sp_h is not None:
            home_starter = sp_h
        if sp_a is not None:
            away_starter = sp_a

    await _set_local_statement_timeout_for_mlb_write(session)
    result = await session.execute(select(Game).where(Game.game_pk == item["game_pk"]))
    game = result.scalar_one_or_none()

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
            home_starter_id=home_starter,
            away_starter_id=away_starter,
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
            if game.lineups_json is None or _json_repr_for_compare(
                game.lineups_json
            ) != _json_repr_for_compare(lineups_json):
                game.lineups_json = lineups_json
        if boxscore_json is not None:
            if game.boxscore_json is None or _json_repr_for_compare(
                game.boxscore_json
            ) != _json_repr_for_compare(boxscore_json):
                game.boxscore_json = boxscore_json
        if home_starter is not None:
            game.home_starter_id = home_starter
        if away_starter is not None:
            game.away_starter_id = away_starter

    await session.flush()
    return game


async def sync_games_for_date(
    session: AsyncSession,
    client: MlbApiClient,
    date_str: str,
    *,
    fetch_details: bool = True,
) -> list[Game]:
    raw = await client.schedule(date_str)
    parsed = parse_schedule_games(raw)
    await _set_local_statement_timeout_for_mlb_write(session)
    await _upsert_teams_for_full_schedule(session, parsed)
    await session.flush()

    valid_items = [item for item in parsed if item.get("home_team_id") is not None and item.get("away_team_id") is not None]

    existing_by_pk: dict[int, Game] = {}
    if valid_items:
        load_pks = [int(item["game_pk"]) for item in valid_items]
        ex_res = await session.execute(select(Game).where(Game.game_pk.in_(load_pks)))
        for row in ex_res.scalars().all():
            existing_by_pk[row.game_pk] = row

    prefetched_data: dict[int, tuple[Any, Any, Any]] = {}
    if fetch_details:

        async def _fetch_all(item: dict[str, Any]) -> tuple[int, Any, Any, Any]:
            pk = item["game_pk"]
            st = str(item.get("status") or "").lower()
            is_final = _is_final_schedule_status(st)
            row = existing_by_pk.get(pk)
            if (
                row is not None
                and is_final
                and row.boxscore_json is not None
                and row.home_score is not None
                and row.away_score is not None
            ):
                return pk, row.boxscore_json, None, None

            box = live = ls = None
            if is_final:
                try:
                    box = await client.boxscore(pk)
                except Exception:
                    pass
            else:
                try:
                    box = await client.boxscore(pk)
                except Exception:
                    pass
                try:
                    live = await client.live_feed(pk)
                except Exception:
                    pass

            hs, aws = item.get("home_score"), item.get("away_score")
            if hs is None or aws is None:
                needs_ls = True
                if box:
                    bh, ba = _scores_from_boxscore(box)
                    if (hs is not None or bh is not None) and (aws is not None or ba is not None):
                        needs_ls = False
                if needs_ls:
                    try:
                        ls = await client.linescore(pk)
                    except Exception:
                        pass
            return pk, box, live, ls

        results = await asyncio.gather(*(_fetch_all(it) for it in valid_items))
        for pk, box, live, ls in results:
            prefetched_data[pk] = (box, live, ls)
            
    games: list[Game] = []
    for item in valid_items:
        pk = item["game_pk"]
        box, live, ls = prefetched_data.get(pk, (None, None, None))
        g = await _upsert_game_from_schedule_item(
            session,
            client,
            item,
            fetch_details=fetch_details,
            skip_team_upsert=True,
            prefetched_boxscore=box,
            prefetched_live_feed=live,
            prefetched_linescore=ls,
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
    raw = await client.schedule_for_game(game_pk)
    parsed = parse_schedule_games(raw)
    item = next((x for x in parsed if x["game_pk"] == game_pk), None)
    if item is None:
        return None
    return await _upsert_game_from_schedule_item(
        session, client, item, fetch_details=fetch_details
    )
