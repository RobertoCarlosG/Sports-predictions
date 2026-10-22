"""Regenera ``src/app/data/mlb_stadiums.json`` desde statsapi (coordenadas, elevación, techo).

Incluye los estadios de los partidos en BD y las casas actuales de los 30 equipos. Si MLB no trae
coordenadas (p. ej. sedes internacionales), geocodifica la ciudad con Open-Meteo.

Uso (desde ``backend/``):

  python -m app.cli.refresh_stadiums
  python -m app.cli.refresh_stadiums --output src/app/data/mlb_stadiums.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import async_session_factory
from app.models.mlb import Game
from app.services.mlb_client import MlbApiClient
from app.services.stadiums import resolve_stadium_data_file

log = logging.getLogger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FEET_TO_M = 0.3048
_DEFAULT = {"lat": 39.8283, "lon": -98.5795, "name": "US center (fallback)"}


def venue_entry(venue: dict[str, Any]) -> dict[str, Any] | None:
    """Entrada del JSON desde un venue de statsapi; ``None`` si no trae coordenadas."""
    loc = venue.get("location") or {}
    coords = loc.get("defaultCoordinates") or {}
    if coords.get("latitude") is None or coords.get("longitude") is None:
        return None
    elevation_ft = loc.get("elevation")
    return {
        "lat": float(coords["latitude"]),
        "lon": float(coords["longitude"]),
        "name": venue.get("name"),
        "elevation_m": round(float(elevation_ft) * FEET_TO_M, 1) if elevation_ft is not None else None,
        "roof_type": (venue.get("fieldInfo") or {}).get("roofType"),
    }


async def _geocode_city(client: httpx.AsyncClient, venue: dict[str, Any]) -> dict[str, Any] | None:
    city = (venue.get("location") or {}).get("city")
    if not city:
        return None
    r = await client.get(GEOCODING_URL, params={"name": city, "count": 1})
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        return None
    hit = results[0]
    return {
        "lat": float(hit["latitude"]),
        "lon": float(hit["longitude"]),
        "name": venue.get("name"),
        "elevation_m": hit.get("elevation"),
        "roof_type": (venue.get("fieldInfo") or {}).get("roofType"),
        "geocoded_city": city,
    }


async def _elevation_m(client: httpx.AsyncClient, lat: float, lon: float) -> float | None:
    r = await client.get(
        f"{settings.open_meteo_base_url.rstrip('/')}/elevation", params={"latitude": lat, "longitude": lon}
    )
    r.raise_for_status()
    values = r.json().get("elevation") or []
    return float(values[0]) if values else None


async def _collect() -> tuple[dict[str, Any], int]:
    async with async_session_factory() as session:
        ids = {int(v) for v in (await session.execute(select(Game.venue_id).distinct())).scalars() if v is not None}
    async with httpx.AsyncClient(timeout=30.0) as client:
        teams = (await client.get(f"{settings.mlb_api_base_url}/teams", params={"sportId": 1})).json()
        ids |= {int(t["venue"]["id"]) for t in teams.get("teams", []) if (t.get("venue") or {}).get("id")}
        mlb = MlbApiClient(settings.mlb_api_base_url, client)
        venues: dict[str, Any] = {}
        for venue in await mlb.venues(sorted(ids)):
            entry = venue_entry(venue) or await _geocode_city(client, venue)
            if entry is None:
                log.warning("sin coordenadas: venue_id=%s %s", venue.get("id"), venue.get("name"))
                continue
            if entry.get("elevation_m") is None:
                entry["elevation_m"] = await _elevation_m(client, entry["lat"], entry["lon"])
            venues[str(venue["id"])] = entry
    data = {"default": _DEFAULT, "venues": dict(sorted(venues.items(), key=lambda kv: int(kv[0])))}
    return data, len(ids)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Regenera mlb_stadiums.json desde statsapi.")
    p.add_argument("--output", default=None, help="Ruta del JSON (default: el que usa la API)")
    args = p.parse_args(argv)
    output = Path(args.output) if args.output else resolve_stadium_data_file(settings.mlb_stadiums_path)
    data, n_ids = asyncio.run(_collect())
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("escritos %d estadios en %s (de %d ids)", len(data["venues"]), output, n_ids)


if __name__ == "__main__":
    main()
