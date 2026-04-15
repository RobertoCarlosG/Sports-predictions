from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast


@dataclass(frozen=True)
class StadiumCoords:
    lat: float
    lon: float
    name: str | None = None


def load_stadium_index(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def resolve_stadium_data_file(stadiums_path: str) -> Path:
    """Resolve JSON path; fall back to packaged `data/mlb_stadiums.json`."""
    path = Path(stadiums_path)
    if path.is_file():
        return path
    return Path(__file__).resolve().parent.parent / "data" / "mlb_stadiums.json"


def coords_for_venue(data: dict[str, Any], venue_id: int | None) -> StadiumCoords:
    default = data.get("default") or {}
    d_lat = float(default.get("lat", 39.8283))
    d_lon = float(default.get("lon", -98.5795))
    d_name = default.get("name")
    if venue_id is None:
        return StadiumCoords(lat=d_lat, lon=d_lon, name=str(d_name) if d_name else None)
    key = str(venue_id)
    venues: dict[str, Any] = data.get("venues") or {}
    v = venues.get(key)
    if not v:
        return StadiumCoords(lat=d_lat, lon=d_lon, name=str(d_name) if d_name else None)
    return StadiumCoords(
        lat=float(v["lat"]),
        lon=float(v["lon"]),
        name=v.get("name"),
    )
