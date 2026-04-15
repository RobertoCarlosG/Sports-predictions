from __future__ import annotations

import datetime as dt
from typing import Any, cast

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mlb import GameWeather
from app.services.stadiums import (
    StadiumCoords,
    coords_for_venue,
    load_stadium_index,
    resolve_stadium_data_file,
)


async def fetch_elevation_m(
    client: httpx.AsyncClient,
    base_url: str,
    coords: StadiumCoords,
) -> float | None:
    r = await client.get(
        f"{base_url.rstrip('/')}/elevation",
        params={"latitude": coords.lat, "longitude": coords.lon},
    )
    r.raise_for_status()
    data = cast(dict[str, Any], r.json())
    elevations = data.get("elevation") or []
    if not elevations:
        return None
    return float(elevations[0])


async def fetch_current_conditions(
    client: httpx.AsyncClient,
    base_url: str,
    coords: StadiumCoords,
) -> dict[str, Any]:
    r = await client.get(
        f"{base_url.rstrip('/')}/forecast",
        params={
            "latitude": coords.lat,
            "longitude": coords.lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure",
            "timezone": "auto",
        },
    )
    r.raise_for_status()
    return cast(dict[str, Any], r.json())


async def upsert_weather_for_game(
    session: AsyncSession,
    *,
    game_pk: int,
    venue_id: int | None,
    stadiums_path: str,
    open_meteo_base: str,
    client: httpx.AsyncClient,
) -> GameWeather | None:
    path = resolve_stadium_data_file(stadiums_path)
    stadium_data = load_stadium_index(path)
    coords = coords_for_venue(stadium_data, venue_id)

    elev = await fetch_elevation_m(client, open_meteo_base, coords)
    wx = await fetch_current_conditions(client, open_meteo_base, coords)
    current = wx.get("current") or {}
    now = dt.datetime.now(dt.UTC)

    temperature_c = current.get("temperature_2m")
    humidity_pct = current.get("relative_humidity_2m")
    wind_mps = current.get("wind_speed_10m")
    pressure = current.get("surface_pressure")

    result = await session.execute(select(GameWeather).where(GameWeather.game_pk == game_pk))
    row = result.scalar_one_or_none()
    payload = {"elevation_m": elev, "open_meteo": wx}
    if row is None:
        row = GameWeather(
            game_pk=game_pk,
            temperature_c=float(temperature_c) if temperature_c is not None else None,
            humidity_pct=float(humidity_pct) if humidity_pct is not None else None,
            wind_speed_mps=float(wind_mps) if wind_mps is not None else None,
            pressure_mbar=float(pressure) if pressure is not None else None,
            elevation_m=elev,
            raw_json=payload,
            fetched_at=now,
        )
        session.add(row)
    else:
        row.temperature_c = float(temperature_c) if temperature_c is not None else row.temperature_c
        row.humidity_pct = float(humidity_pct) if humidity_pct is not None else row.humidity_pct
        row.wind_speed_mps = float(wind_mps) if wind_mps is not None else row.wind_speed_mps
        row.pressure_mbar = float(pressure) if pressure is not None else row.pressure_mbar
        row.elevation_m = elev if elev is not None else row.elevation_m
        row.raw_json = payload
        row.fetched_at = now
    await session.flush()
    return row
