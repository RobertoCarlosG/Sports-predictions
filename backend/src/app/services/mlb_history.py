from __future__ import annotations

import datetime as dt

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mlb import Game


def compute_winner_team_id(
    home_team_id: int,
    away_team_id: int,
    home_score: int | None,
    away_score: int | None,
) -> int | None:
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return home_team_id
    if away_score > home_score:
        return away_team_id
    return None


async def query_mlb_history(
    session: AsyncSession,
    *,
    season: str | None,
    team_id: int | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    only_final: bool,
    only_with_scores: bool,
    limit: int,
    offset: int,
) -> list[Game]:
    q = select(Game).options(selectinload(Game.home_team), selectinload(Game.away_team))
    if season:
        q = q.where(Game.season == season)
    if team_id is not None:
        q = q.where(or_(Game.home_team_id == team_id, Game.away_team_id == team_id))
    if date_from is not None:
        q = q.where(Game.game_date >= date_from)
    if date_to is not None:
        q = q.where(Game.game_date <= date_to)
    if only_final:
        q = q.where(Game.status == "Final")
    if only_with_scores:
        q = q.where(Game.home_score.is_not(None), Game.away_score.is_not(None))
    q = q.order_by(Game.game_date.desc(), Game.game_pk.desc())
    q = q.limit(limit).offset(offset)
    result = await session.execute(q)
    return list(result.scalars().unique().all())
