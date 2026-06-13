"""Liga (AL/NL) y división por team id de MLB (statsapi.mlb.com /teams?sportId=1).

La afiliación liga/división es estática para los 30 equipos activos, así que se
mantiene como mapa local en lugar de pedirla al API. Se usa para segmentar
partidos y rellenar `teams.league` / `teams.division` durante el sync."""
from __future__ import annotations

from app.data.mlb_team_abbreviations import mlb_team_id_to_int

# Etiquetas canónicas de liga.
LEAGUE_AL = "AL"
LEAGUE_NL = "NL"

# team_id -> (liga, división)
MLB_TEAM_ID_TO_LEAGUE_DIVISION: dict[int, tuple[str, str]] = {
    # AL East
    110: (LEAGUE_AL, "AL East"),    # BAL
    111: (LEAGUE_AL, "AL East"),    # BOS
    139: (LEAGUE_AL, "AL East"),    # TB
    141: (LEAGUE_AL, "AL East"),    # TOR
    147: (LEAGUE_AL, "AL East"),    # NYY
    # AL Central
    114: (LEAGUE_AL, "AL Central"),  # CLE
    116: (LEAGUE_AL, "AL Central"),  # DET
    118: (LEAGUE_AL, "AL Central"),  # KC
    142: (LEAGUE_AL, "AL Central"),  # MIN
    145: (LEAGUE_AL, "AL Central"),  # CWS
    # AL West
    108: (LEAGUE_AL, "AL West"),    # LAA
    117: (LEAGUE_AL, "AL West"),    # HOU
    133: (LEAGUE_AL, "AL West"),    # ATH
    136: (LEAGUE_AL, "AL West"),    # SEA
    140: (LEAGUE_AL, "AL West"),    # TEX
    # NL East
    120: (LEAGUE_NL, "NL East"),    # WSH
    121: (LEAGUE_NL, "NL East"),    # NYM
    143: (LEAGUE_NL, "NL East"),    # PHI
    144: (LEAGUE_NL, "NL East"),    # ATL
    146: (LEAGUE_NL, "NL East"),    # MIA
    # NL Central
    112: (LEAGUE_NL, "NL Central"),  # CHC
    113: (LEAGUE_NL, "NL Central"),  # CIN
    134: (LEAGUE_NL, "NL Central"),  # PIT
    138: (LEAGUE_NL, "NL Central"),  # STL
    158: (LEAGUE_NL, "NL Central"),  # MIL
    # NL West
    109: (LEAGUE_NL, "NL West"),    # AZ
    115: (LEAGUE_NL, "NL West"),    # COL
    119: (LEAGUE_NL, "NL West"),    # LAD
    135: (LEAGUE_NL, "NL West"),    # SD
    137: (LEAGUE_NL, "NL West"),    # SF
}

# Estructura liga -> divisiones, para construir filtros en el cliente.
MLB_LEAGUE_STRUCTURE: dict[str, list[str]] = {
    LEAGUE_AL: ["AL East", "AL Central", "AL West"],
    LEAGUE_NL: ["NL East", "NL Central", "NL West"],
}


def league_division_for(team_id: object) -> tuple[str, str] | None:
    """Devuelve (liga, división) para un team id, o None si no se reconoce."""
    tid = mlb_team_id_to_int(team_id)
    if tid is None:
        return None
    return MLB_TEAM_ID_TO_LEAGUE_DIVISION.get(tid)
