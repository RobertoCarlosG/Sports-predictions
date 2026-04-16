"""Abreviaturas MLB por team id (statsapi.mlb.com /teams?sportId=1).

Sirve de respaldo cuando el schedule sin hydrate o filas viejas en BD tienen HOME/AWAY."""
from __future__ import annotations

from typing import Any


def mlb_team_id_to_int(team_id: Any) -> int | None:
    """Normaliza id de equipo para lookup: SQLAlchemy/JSON a veces devuelven float (110.0) y
    `110.0 in {110: ...}` es False en Python."""
    if team_id is None or type(team_id) is bool:
        return None
    if isinstance(team_id, int):
        return team_id
    if isinstance(team_id, float):
        if team_id != team_id:  # NaN
            return None
        r = round(team_id)
        return r if abs(team_id - r) < 1e-9 else None
    try:
        return int(str(team_id).strip())
    except (TypeError, ValueError):
        return None


# IDs activos MLB; valores = campo `abbreviation` del API de equipos.
MLB_TEAM_ID_TO_ABBR: dict[int, str] = {
    108: "LAA",
    109: "AZ",
    110: "BAL",
    111: "BOS",
    112: "CHC",
    113: "CIN",
    114: "CLE",
    115: "COL",
    116: "DET",
    117: "HOU",
    118: "KC",
    119: "LAD",
    120: "WSH",
    121: "NYM",
    133: "ATH",
    134: "PIT",
    135: "SD",
    136: "SEA",
    137: "SF",
    138: "STL",
    139: "TB",
    140: "TEX",
    141: "TOR",
    142: "MIN",
    143: "PHI",
    144: "ATL",
    145: "CWS",
    146: "MIA",
    147: "NYY",
    158: "MIL",
}


def team_abbr_for_display(team_id: Any, parsed_abbr: str, full_name: str = "") -> str:
    """Abreviatura para persistir y mostrar: mapa por id, luego API, luego apodo del nombre."""
    tid = mlb_team_id_to_int(team_id)
    if tid is not None and tid in MLB_TEAM_ID_TO_ABBR:
        return MLB_TEAM_ID_TO_ABBR[tid]
    p = (parsed_abbr or "").strip().upper()
    if p and p not in {"HOME", "AWAY"}:
        return p[:8]
    parts = full_name.strip().split()
    if parts:
        return parts[-1][:8].upper()
    return "?"
