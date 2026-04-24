"""ERA de abridores (people) y del staff (teams) vía API MLB, con caché en `pitching_era_cache`."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mlb import PitchingEraCache
from app.services.mlb_client import MlbApiClient

KIND_PLAYER = "P"
KIND_TEAM = "T"
DEFAULT_ERA = 4.5
DEFAULT_STAFF_ERA = 4.2


async def get_cached_era(
    session: AsyncSession, kind: str, ref_id: int, season: str
) -> float | None:
    row = (
        await session.execute(
            select(PitchingEraCache.era).where(
                PitchingEraCache.kind == kind,
                PitchingEraCache.ref_id == ref_id,
                PitchingEraCache.season == season,
            )
        )
    ).scalar_one_or_none()
    return float(row) if row is not None else None


async def put_cached_era(
    session: AsyncSession, kind: str, ref_id: int, season: str, era: float
) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    row = (
        await session.execute(
            select(PitchingEraCache).where(
                PitchingEraCache.kind == kind,
                PitchingEraCache.ref_id == ref_id,
                PitchingEraCache.season == season,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        session.add(
            PitchingEraCache(
                kind=kind,
                ref_id=ref_id,
                season=season,
                era=era,
                updated_at=now,
            )
        )
    else:
        row.era = era
        row.updated_at = now


async def get_pitcher_era(
    session: AsyncSession, client: MlbApiClient | None, person_id: int, season: str
) -> float:
    c = await get_cached_era(session, KIND_PLAYER, person_id, season)
    if c is not None:
        return c
    if client is None:
        return DEFAULT_ERA
    live = await client.person_season_pitching_era(person_id, season)
    era = float(live) if live is not None else DEFAULT_ERA
    await put_cached_era(session, KIND_PLAYER, person_id, season, era)
    return era


async def get_team_pitching_era(
    session: AsyncSession, client: MlbApiClient | None, team_id: int, season: str
) -> float:
    """ERA colectivo del pitcheo del equipo (Stats API no separa solo bullpen en un solo campo fiable)."""
    c = await get_cached_era(session, KIND_TEAM, team_id, season)
    if c is not None:
        return c
    if client is None:
        return DEFAULT_STAFF_ERA
    live = await client.team_season_pitching_era(team_id, season)
    era = float(live) if live is not None else DEFAULT_STAFF_ERA
    await put_cached_era(session, KIND_TEAM, team_id, season, era)
    return era


async def game_pitching_feature_values(
    session: AsyncSession,
    mlb: MlbApiClient | None,
    *,
    season: str,
    home_team_id: int,
    away_team_id: int,
    home_starter_id: int | None,
    away_starter_id: int | None,
) -> tuple[float, float, float, float]:
    """
    (home_starter_era, away_starter_era, home_bullpen_era, away_bullpen_era)
    *bullpen* = staff ERA (toda la plantilla) como proxy; el split exacto de relevistas
    requiere más datos o otra API.
    """
    hs = home_starter_id
    a_s = away_starter_id
    h_se = await get_pitcher_era(session, mlb, hs, season) if hs is not None else DEFAULT_ERA
    a_se = await get_pitcher_era(session, mlb, a_s, season) if a_s is not None else DEFAULT_ERA
    h_be = await get_team_pitching_era(session, mlb, home_team_id, season)
    a_be = await get_team_pitching_era(session, mlb, away_team_id, season)
    return h_se, a_se, h_be, a_be
