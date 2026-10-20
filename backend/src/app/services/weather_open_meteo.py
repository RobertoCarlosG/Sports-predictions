"""Clima del estadio a la hora de inicio de cada partido (Open-Meteo, sin API key).

- Fechas pasadas: API histórica (``/archive``); futuras: pronóstico (``/forecast``, hoy−92 … hoy+15).
- Una petición por estadio y rango de fechas (no una por partido): ~30 estadios por temporada.
- Coordenadas, elevación y techo vienen de ``mlb_stadiums.json`` (``python -m app.cli.refresh_stadiums``);
  un estadio que no esté en el JSON se omite en lugar de usar coordenadas de otra ciudad.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, cast

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.mlb import Game, GameWeather, game_payload_deferred
from app.services.stadiums import (
    StadiumCoords,
    known_venue_coords,
    load_stadium_index,
    resolve_stadium_data_file,
)

log = logging.getLogger(__name__)

HOURLY_VARS = ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "surface_pressure")
FORECAST_MAX_PAST_DAYS = 92
FORECAST_MAX_FUTURE_DAYS = 15
# Sin hora en el schedule: 23:00 UTC ≈ 19:00 ET, inicio nocturno típico.
_DEFAULT_START_HOUR_UTC = 23


@dataclass(frozen=True)
class HourlyConditions:
    temperature_c: float | None
    humidity_pct: float | None
    wind_speed_mps: float | None
    pressure_mbar: float | None


# Clave "YYYY-MM-DDTHH:00" en UTC (formato de Open-Meteo con timezone=GMT).
HourlySeries = dict[str, HourlyConditions]


@dataclass
class WeatherBackfillResult:
    updated: int = 0
    unknown_venue: int = 0
    no_data: int = 0


def _hour_key(ts: dt.datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:00")


def game_hour_utc(game: Game) -> dt.datetime:
    """Hora de inicio redondeada a la hora más cercana (UTC)."""
    ts = game.game_datetime_utc
    if ts is None:
        return dt.datetime.combine(game.game_date, dt.time(_DEFAULT_START_HOUR_UTC), tzinfo=dt.UTC)
    ts = ts.replace(tzinfo=dt.UTC) if ts.tzinfo is None else ts.astimezone(dt.UTC)
    rounded = ts.replace(minute=0, second=0, microsecond=0)
    return rounded + dt.timedelta(hours=1) if ts.minute >= 30 else rounded


async def fetch_hourly(
    client: httpx.AsyncClient,
    base_url: str,
    endpoint: str,
    coords: StadiumCoords,
    start: dt.date,
    end: dt.date,
) -> HourlySeries:
    """Serie horaria [start, end] para unas coordenadas (``endpoint``: "archive" o "forecast")."""
    r = await client.get(
        f"{base_url.rstrip('/')}/{endpoint}",
        params={
            "latitude": coords.lat,
            "longitude": coords.lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(HOURLY_VARS),
            "wind_speed_unit": "ms",  # el default de Open-Meteo es km/h
            "timezone": "GMT",
        },
    )
    r.raise_for_status()
    hourly = cast(dict[str, Any], r.json()).get("hourly") or {}
    times: list[str] = hourly.get("time") or []
    columns = [hourly.get(var) or [] for var in HOURLY_VARS]
    out: HourlySeries = {}
    for i, t in enumerate(times):
        values = [col[i] if i < len(col) else None for col in columns]
        if all(v is None for v in values):
            continue  # el histórico tiene unos días de retraso
        out[t] = HourlyConditions(*(float(v) if v is not None else None for v in values))
    return out


async def _venue_series(
    client: httpx.AsyncClient,
    coords: StadiumCoords,
    hours: list[dt.datetime],
    today: dt.date,
) -> tuple[HourlySeries, HourlySeries]:
    """(histórico, pronóstico) que cubren ``hours``; el pronóstico solo para horas futuras o sin histórico."""
    archive: HourlySeries = {}
    past = sorted({h.date() for h in hours if h.date() <= today})
    if past:
        archive = await fetch_hourly(client, settings.open_meteo_archive_base_url, "archive", coords, past[0], past[-1])
    lo = today - dt.timedelta(days=FORECAST_MAX_PAST_DAYS)
    hi = today + dt.timedelta(days=FORECAST_MAX_FUTURE_DAYS)
    pending = sorted({h.date() for h in hours if _hour_key(h) not in archive and lo <= h.date() <= hi})
    forecast: HourlySeries = {}
    if pending:
        forecast = await fetch_hourly(client, settings.open_meteo_base_url, "forecast", coords, pending[0], pending[-1])
    return archive, forecast


async def backfill_weather_for_games(
    session: AsyncSession,
    games: Sequence[Game],
    *,
    client: httpx.AsyncClient,
    stadiums_path: str | None = None,
    today: dt.date | None = None,
) -> WeatherBackfillResult:
    """Guarda en `game_weather` las condiciones a la hora de inicio de cada partido (agrupa por estadio)."""
    today = today or dt.datetime.now(dt.UTC).date()
    data = load_stadium_index(resolve_stadium_data_file(stadiums_path or settings.mlb_stadiums_path))
    result = WeatherBackfillResult()

    by_venue: dict[int, list[Game]] = defaultdict(list)
    venue_coords: dict[int, StadiumCoords] = {}
    for g in games:
        coords = known_venue_coords(data, g.venue_id)
        if coords is None or g.venue_id is None:
            result.unknown_venue += 1
            continue
        by_venue[g.venue_id].append(g)
        venue_coords[g.venue_id] = coords
    if not by_venue:
        return result

    pks = [g.game_pk for vg in by_venue.values() for g in vg]
    existing = {
        w.game_pk: w for w in (await session.execute(select(GameWeather).where(GameWeather.game_pk.in_(pks)))).scalars()
    }
    now = dt.datetime.now(dt.UTC)

    for venue_id, venue_games in by_venue.items():
        coords = venue_coords[venue_id]
        hours = {g.game_pk: game_hour_utc(g) for g in venue_games}
        try:
            archive, forecast = await _venue_series(client, coords, list(hours.values()), today)
        except httpx.HTTPError:
            log.warning("Open-Meteo falló para venue_id=%s (%s)", venue_id, coords.name, exc_info=True)
            result.no_data += len(venue_games)
            continue
        for g in venue_games:
            key = _hour_key(hours[g.game_pk])
            source = "archive" if key in archive else "forecast"
            cond = archive.get(key) or forecast.get(key)
            if cond is None:
                result.no_data += 1  # fuera de la ventana de Open-Meteo (p. ej. > 15 días)
                continue
            row = existing.get(g.game_pk)
            if row is None:
                row = GameWeather(game_pk=g.game_pk, fetched_at=now)
                session.add(row)
                existing[g.game_pk] = row
            row.temperature_c = cond.temperature_c
            row.humidity_pct = cond.humidity_pct
            row.wind_speed_mps = cond.wind_speed_mps
            row.pressure_mbar = cond.pressure_mbar
            row.elevation_m = coords.elevation_m
            row.raw_json = {
                "source": f"open-meteo/{source}",
                "hour_utc": key,
                "venue": coords.name,
                "roof_type": coords.roof_type,
                "lat": coords.lat,
                "lon": coords.lon,
            }
            row.fetched_at = now
            result.updated += 1
    await session.flush()
    return result


async def backfill_weather_for_range(
    session: AsyncSession,
    *,
    start: dt.date,
    end: dt.date,
    client: httpx.AsyncClient,
    season: str | None = None,
    only_missing: bool = False,
) -> WeatherBackfillResult:
    """Clima de los partidos con ``game_date`` en [start, end] (opcional: solo los que no tienen fila)."""
    stmt = select(Game).where(Game.game_date.between(start, end)).options(*game_payload_deferred())
    if season is not None:
        stmt = stmt.where(Game.season == season)
    if only_missing:
        stmt = stmt.where(~select(GameWeather.id).where(GameWeather.game_pk == Game.game_pk).exists())
    games = list((await session.execute(stmt)).scalars().all())
    res = await backfill_weather_for_games(session, games, client=client)
    log.info(
        "weather %s..%s: %d actualizados, %d sin estadio en JSON, %d sin datos",
        start,
        end,
        res.updated,
        res.unknown_venue,
        res.no_data,
    )
    return res


async def upsert_weather_for_game(
    session: AsyncSession,
    *,
    game: Game,
    client: httpx.AsyncClient,
) -> GameWeather | None:
    """Clima a la hora de inicio de un partido (botón «Actualizar datos» del detalle)."""
    await backfill_weather_for_games(session, [game], client=client)
    return (await session.execute(select(GameWeather).where(GameWeather.game_pk == game.game_pk))).scalar_one_or_none()
