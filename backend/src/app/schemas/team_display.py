from __future__ import annotations

from app.data.mlb_league_division import league_division_for
from app.data.mlb_team_abbreviations import team_abbr_for_display
from app.models.mlb import Team
from app.schemas.games import TeamOut


def team_out_from_model(team: Team) -> TeamOut:
    """TeamOut con abreviatura corregida aunque la fila tenga HOME/AWAY de syncs viejos."""
    abbr = team_abbr_for_display(team.id, team.abbreviation, team.name)
    # Respaldo: si la fila aún no tiene liga/división (sync viejo), la deriva del mapa.
    league = team.league
    division = team.division
    if league is None or division is None:
        ld = league_division_for(team.id)
        if ld is not None:
            league = league or ld[0]
            division = division or ld[1]
    return TeamOut(
        id=team.id,
        name=team.name,
        abbreviation=abbr,
        league=league,
        division=division,
    )
