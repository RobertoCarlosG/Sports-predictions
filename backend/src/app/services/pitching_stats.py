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

# (kind, ref_id, season) → ERA. Precargado con ``load_era_memo``; evita 4 SELECT por partido.
EraMemo = dict[tuple[str, int, str], float]


async def load_era_memo(session: AsyncSession) -> EraMemo:
    """Lee toda `pitching_era_cache` (cientos de filas) de una vez para procesos por lotes."""
    rows = await session.execute(
        select(PitchingEraCache.kind, PitchingEraCache.ref_id, PitchingEraCache.season, PitchingEraCache.era)
    )
    return {(kind, int(ref_id), season): float(era) for kind, ref_id, season, era in rows.all()}


async def get_cached_era(
    session: AsyncSession,
    kind: str,
    ref_id: int,
    season: str,
    *,
    memo: EraMemo | None = None,
) -> float | None:
    if memo is not None:
        # Con memo precargado, una ausencia equivale a «no está en BD».
        return memo.get((kind, ref_id, season))
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
    session: AsyncSession,
    kind: str,
    ref_id: int,
    season: str,
    era: float,
    *,
    memo: EraMemo | None = None,
) -> None:
    if memo is not None:
        memo[(kind, ref_id, season)] = era
    now = dt.datetime.now(dt.UTC)
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
    session: AsyncSession,
    client: MlbApiClient | None,
    person_id: int,
    season: str,
    *,
    commit_before_mlb: bool = False,
    memo: EraMemo | None = None,
) -> float:
    c = await get_cached_era(session, KIND_PLAYER, person_id, season, memo=memo)
    if c is not None:
        return c
    if client is None:
        return DEFAULT_ERA
    if commit_before_mlb:
        # PgBouncer/Supabase suelen matar conexión si hay HTTP larga con la tx abierta.
        await session.commit()
    live = await client.person_season_pitching_era(person_id, season)
    era = float(live) if live is not None else DEFAULT_ERA
    await put_cached_era(session, KIND_PLAYER, person_id, season, era, memo=memo)
    return era


async def get_team_pitching_era(
    session: AsyncSession,
    client: MlbApiClient | None,
    team_id: int,
    season: str,
    *,
    commit_before_mlb: bool = False,
    memo: EraMemo | None = None,
) -> float:
    """ERA colectivo del pitcheo del equipo.

    Stats API no separa solo bullpen en un solo campo fiable.
    """
    c = await get_cached_era(session, KIND_TEAM, team_id, season, memo=memo)
    if c is not None:
        return c
    if client is None:
        return DEFAULT_STAFF_ERA
    if commit_before_mlb:
        await session.commit()
    live = await client.team_season_pitching_era(team_id, season)
    era = float(live) if live is not None else DEFAULT_STAFF_ERA
    await put_cached_era(session, KIND_TEAM, team_id, season, era, memo=memo)
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
    commit_before_mlb: bool = False,
    era_memo: EraMemo | None = None,
) -> tuple[float, float, float, float]:
    """
    (home_starter_era, away_starter_era, home_bullpen_era, away_bullpen_era)
    *bullpen* = staff ERA (toda la plantilla) como proxy; el split exacto de relevistas
    requiere más datos o otra API.
    *commit_before_mlb*: activar en tareas largas (p. ej. ``rebuild_game_feature_snapshots``)
    para no mantener transacción abierta durante muchas idas a la red MLB; evita
    ``ConnectionDoesNotExist`` con PgBouncer/Supabase.
    *era_memo*: caché en memoria de ``load_era_memo`` (lotes); sin él, un SELECT por valor.
    """
    hs = home_starter_id
    a_s = away_starter_id
    c = commit_before_mlb
    m = era_memo
    h_se = DEFAULT_ERA if hs is None else await get_pitcher_era(session, mlb, hs, season, commit_before_mlb=c, memo=m)
    a_se = DEFAULT_ERA if a_s is None else await get_pitcher_era(session, mlb, a_s, season, commit_before_mlb=c, memo=m)
    h_be = await get_team_pitching_era(session, mlb, home_team_id, season, commit_before_mlb=c, memo=m)
    a_be = await get_team_pitching_era(session, mlb, away_team_id, season, commit_before_mlb=c, memo=m)
    return h_se, a_se, h_be, a_be
