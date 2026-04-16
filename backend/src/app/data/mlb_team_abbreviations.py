"""Abreviaturas MLB por team id (statsapi.mlb.com /teams?sportId=1).

Sirve de respaldo cuando el schedule sin hydrate o filas viejas en BD tienen HOME/AWAY."""
from __future__ import annotations

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


def team_abbr_for_display(team_id: int, parsed_abbr: str, full_name: str = "") -> str:
    """Abreviatura para persistir y mostrar: mapa por id, luego API, luego apodo del nombre."""
    if team_id in MLB_TEAM_ID_TO_ABBR:
        return MLB_TEAM_ID_TO_ABBR[team_id]
    p = (parsed_abbr or "").strip().upper()
    if p and p not in {"HOME", "AWAY"}:
        return p[:8]
    parts = full_name.strip().split()
    if parts:
        return parts[-1][:8].upper()
    return "?"
