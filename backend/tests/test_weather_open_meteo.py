"""Clima por partido a la hora de inicio (Open-Meteo histórico + pronóstico), sin red."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.cli.refresh_stadiums import venue_entry
from app.models.mlb import Game, GameWeather, Team
from app.services.stadiums import known_venue_coords
from app.services.weather_open_meteo import (
    backfill_weather_for_games,
    fetch_hourly,
    game_hour_utc,
)

TODAY = dt.date(2026, 10, 20)


def _game(pk: int, venue_id: int | None, start: dt.datetime | None, day: dt.date | None = None) -> Game:
    return Game(
        game_pk=pk,
        season="2026",
        game_date=day or (start.date() if start else TODAY),
        game_datetime_utc=start,
        status="Scheduled",
        home_team_id=1,
        away_team_id=2,
        venue_id=venue_id,
    )


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (dt.datetime(2026, 10, 24, 0, 8, tzinfo=dt.UTC), dt.datetime(2026, 10, 24, 0, tzinfo=dt.UTC)),
        (dt.datetime(2026, 10, 23, 23, 40, tzinfo=dt.UTC), dt.datetime(2026, 10, 24, 0, tzinfo=dt.UTC)),
        (dt.datetime(2026, 10, 23, 17, 5), dt.datetime(2026, 10, 23, 17, tzinfo=dt.UTC)),  # naive (SQLite) = UTC
        (None, dt.datetime(2026, 10, 23, 23, tzinfo=dt.UTC)),  # sin hora: 23:00 UTC del día
    ],
)
def test_game_hour_utc(start: dt.datetime | None, expected: dt.datetime) -> None:
    assert game_hour_utc(_game(1, 32, start, dt.date(2026, 10, 23))) == expected


def _hourly(times: list[str], temp: float = 15.0) -> dict[str, Any]:
    n = len(times)
    return {
        "hourly": {
            "time": times,
            "temperature_2m": [temp] * n,
            "relative_humidity_2m": [60] * n,
            "wind_speed_10m": [2.5] * n,
            "surface_pressure": [1003.0] * n,
        }
    }


@pytest.mark.asyncio
async def test_fetch_hourly_requests_ms_wind_and_skips_empty_hours() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = _hourly(["2026-10-01T00:00", "2026-10-01T01:00"])
        body["hourly"]["time"].append("2026-10-01T02:00")
        for var in ("temperature_2m", "relative_humidity_2m", "wind_speed_10m", "surface_pressure"):
            body["hourly"][var].append(None)  # histórico aún sin publicar
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        coords = known_venue_coords({"venues": {"32": {"lat": 43.0, "lon": -87.9}}}, 32)
        assert coords is not None
        series = await fetch_hourly(
            client, "https://x/v1", "archive", coords, dt.date(2026, 10, 1), dt.date(2026, 10, 1)
        )
    params = seen[0].url.params
    assert seen[0].url.path == "/v1/archive"
    assert params["wind_speed_unit"] == "ms" and params["timezone"] == "GMT"
    assert set(series) == {"2026-10-01T00:00", "2026-10-01T01:00"}
    assert series["2026-10-01T00:00"].wind_speed_mps == 2.5


def test_known_venue_coords_has_no_fallback() -> None:
    data = {"default": {"lat": 1, "lon": 2}, "venues": {"32": {"lat": 43.0, "lon": -87.9, "elevation_m": 182}}}
    assert known_venue_coords(data, 999) is None
    assert known_venue_coords(data, None) is None
    coords = known_venue_coords(data, 32)
    assert coords is not None and coords.elevation_m == 182.0


def test_refresh_stadiums_venue_entry() -> None:
    venue = {
        "id": 19,
        "name": "Coors Field",
        "location": {"defaultCoordinates": {"latitude": 39.756, "longitude": -104.994}, "elevation": 5190},
        "fieldInfo": {"roofType": "Open"},
    }
    entry = venue_entry(venue)
    assert entry == {
        "lat": 39.756,
        "lon": -104.994,
        "name": "Coors Field",
        "elevation_m": 1581.9,
        "roof_type": "Open",
    }
    assert venue_entry({"id": 1, "location": {}}) is None


@pytest.fixture
def stadiums_json(tmp_path: Path) -> str:
    path = tmp_path / "stadiums.json"
    data = {"venues": {"32": {"lat": 43.03, "lon": -87.97, "name": "American Family Field", "elevation_m": 182.0}}}
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.mark.asyncio
async def test_backfill_batches_by_venue_archive_then_forecast(sqlite_session_factory, stadiums_json) -> None:  # type: ignore[no-untyped-def]
    calls: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        calls.append((endpoint, request.url.params["start_date"], request.url.params["end_date"]))
        if endpoint == "archive":
            return httpx.Response(200, json=_hourly(["2026-10-01T23:00", "2026-10-02T23:00"], temp=10.0))
        return httpx.Response(200, json=_hourly(["2026-10-24T00:00"], temp=16.0))

    games = [
        _game(1, 32, dt.datetime(2026, 10, 1, 23, 10, tzinfo=dt.UTC)),  # pasado → histórico
        _game(2, 32, dt.datetime(2026, 10, 2, 23, 5, tzinfo=dt.UTC)),  # pasado → histórico
        _game(3, 32, dt.datetime(2026, 10, 24, 0, 8, tzinfo=dt.UTC)),  # futuro → pronóstico
        _game(4, 32, dt.datetime(2026, 11, 20, 0, 0, tzinfo=dt.UTC)),  # > 15 días: sin datos
        _game(5, 999, dt.datetime(2026, 10, 1, 23, 0, tzinfo=dt.UTC)),  # estadio fuera del JSON
    ]
    async with sqlite_session_factory() as session:
        session.add_all([Team(id=1, name="Home", abbreviation="HOM"), Team(id=2, name="Away", abbreviation="AWY")])
        session.add_all(games)
        await session.commit()

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        for _ in range(2):  # la segunda pasada actualiza filas, no duplica
            async with sqlite_session_factory() as session:
                res = await backfill_weather_for_games(
                    session, games, client=client, stadiums_path=stadiums_json, today=TODAY
                )
                await session.commit()
            assert (res.updated, res.no_data, res.unknown_venue) == (3, 1, 1)

    # Una petición de histórico y una de pronóstico por estadio y pasada (no una por partido); el
    # pronóstico no pide el 2026-11-20 porque cae fuera de su ventana (hoy+15) y la API lo rechazaría.
    assert calls[:2] == [("archive", "2026-10-01", "2026-10-02"), ("forecast", "2026-10-24", "2026-10-24")]
    assert len(calls) == 4

    async with sqlite_session_factory() as session:
        rows = {w.game_pk: w for w in (await session.execute(select(GameWeather))).scalars()}
    assert set(rows) == {1, 2, 3}
    assert rows[1].temperature_c == 10.0 and rows[1].raw_json["source"] == "open-meteo/archive"
    assert rows[3].temperature_c == 16.0 and rows[3].raw_json["source"] == "open-meteo/forecast"
    assert rows[3].raw_json["hour_utc"] == "2026-10-24T00:00"
    assert rows[1].elevation_m == 182.0 and rows[1].wind_speed_mps == 2.5
