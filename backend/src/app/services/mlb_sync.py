from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mlb import Game, Team
from app.services.mlb_client import MlbApiClient, parse_schedule_games


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


async def sync_games_for_date(
    session: AsyncSession,
    client: MlbApiClient,
    date_str: str,
    *,
    fetch_details: bool = True,
) -> list[Game]:
    """Fetch MLB schedule for a date, upsert teams/games, optionally boxscore + live lineups."""
    raw = await client.schedule(date_str)
    parsed = parse_schedule_games(raw)
    games: list[Game] = []

    for item in parsed:
        hid = item.get("home_team_id")
        aid = item.get("away_team_id")
        if hid is None or aid is None:
            continue
        home_name = str(item.get("home_team_name") or "Home")
        away_name = str(item.get("away_team_name") or "Away")
        h_abbr = str(item.get("home_team_abbr") or home_name[:8]).upper()[:8]
        a_abbr = str(item.get("away_team_abbr") or away_name[:8]).upper()[:8]
        await upsert_team(
            session,
            int(hid),
            home_name,
            h_abbr,
            item.get("venue_id"),
            item.get("venue_name"),
        )
        await upsert_team(
            session,
            int(aid),
            away_name,
            a_abbr,
            item.get("venue_id"),
            item.get("venue_name"),
        )

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
            try:
                live = await client.live_feed(item["game_pk"])
                lineups_json = {"liveFeed": live}
            except Exception:
                lineups_json = None

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
                lineups_json=lineups_json,
                boxscore_json=boxscore_json,
            )
            session.add(game)
        else:
            game.status = str(item.get("status") or game.status)
            game.game_datetime_utc = gdt or game.game_datetime_utc
            game.venue_id = item.get("venue_id")
            game.venue_name = item.get("venue_name")
            if lineups_json is not None:
                game.lineups_json = lineups_json
            if boxscore_json is not None:
                game.boxscore_json = boxscore_json
        games.append(game)

    await session.flush()
    return games
