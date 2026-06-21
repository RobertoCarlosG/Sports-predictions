"""Conferencia/división y abreviatura por team id de NBA (stats.nba.com).

La afiliación es estática para los 30 equipos activos, así que se mantiene como
mapa local en lugar de pedirla al API. Se usa para rellenar `nba_teams.conference`
/ `nba_teams.division` y para etiquetas de UI durante el sync.
"""

from __future__ import annotations

CONF_EAST = "East"
CONF_WEST = "West"

# team_id -> (abreviatura, conferencia, división)
NBA_TEAM_META: dict[int, tuple[str, str, str]] = {
    1610612737: ("ATL", CONF_EAST, "Southeast"),
    1610612738: ("BOS", CONF_EAST, "Atlantic"),
    1610612751: ("BKN", CONF_EAST, "Atlantic"),
    1610612766: ("CHA", CONF_EAST, "Southeast"),
    1610612741: ("CHI", CONF_EAST, "Central"),
    1610612739: ("CLE", CONF_EAST, "Central"),
    1610612742: ("DAL", CONF_WEST, "Southwest"),
    1610612743: ("DEN", CONF_WEST, "Northwest"),
    1610612765: ("DET", CONF_EAST, "Central"),
    1610612744: ("GSW", CONF_WEST, "Pacific"),
    1610612745: ("HOU", CONF_WEST, "Southwest"),
    1610612754: ("IND", CONF_EAST, "Central"),
    1610612746: ("LAC", CONF_WEST, "Pacific"),
    1610612747: ("LAL", CONF_WEST, "Pacific"),
    1610612763: ("MEM", CONF_WEST, "Southwest"),
    1610612748: ("MIA", CONF_EAST, "Southeast"),
    1610612749: ("MIL", CONF_EAST, "Central"),
    1610612750: ("MIN", CONF_WEST, "Northwest"),
    1610612740: ("NOP", CONF_WEST, "Southwest"),
    1610612752: ("NYK", CONF_EAST, "Atlantic"),
    1610612760: ("OKC", CONF_WEST, "Northwest"),
    1610612753: ("ORL", CONF_EAST, "Southeast"),
    1610612755: ("PHI", CONF_EAST, "Atlantic"),
    1610612756: ("PHX", CONF_WEST, "Pacific"),
    1610612757: ("POR", CONF_WEST, "Northwest"),
    1610612758: ("SAC", CONF_WEST, "Pacific"),
    1610612759: ("SAS", CONF_WEST, "Southwest"),
    1610612761: ("TOR", CONF_EAST, "Atlantic"),
    1610612762: ("UTA", CONF_WEST, "Northwest"),
    1610612764: ("WAS", CONF_EAST, "Southeast"),
}

# Conferencia -> divisiones, para construir filtros en el cliente.
NBA_CONFERENCE_STRUCTURE: dict[str, list[str]] = {
    CONF_EAST: ["Atlantic", "Central", "Southeast"],
    CONF_WEST: ["Northwest", "Pacific", "Southwest"],
}


def _to_int(team_id: object) -> int | None:
    if team_id is None:
        return None
    try:
        return int(team_id)
    except (TypeError, ValueError):
        return None


def nba_meta_for(team_id: object) -> tuple[str, str, str] | None:
    """Devuelve (abreviatura, conferencia, división) para un team id, o None."""
    tid = _to_int(team_id)
    if tid is None:
        return None
    return NBA_TEAM_META.get(tid)


def nba_abbr_for_display(team_id: object, fallback: str = "") -> str:
    meta = nba_meta_for(team_id)
    if meta is not None:
        return meta[0]
    if fallback.strip():
        return fallback.strip().upper()[:8]
    return "?"
