from __future__ import annotations

from app.data.mlb_team_abbreviations import team_abbr_for_display
from app.models.mlb import Team
from app.schemas.games import TeamOut


def team_out_from_model(team: Team) -> TeamOut:
    """TeamOut con abreviatura corregida aunque la fila tenga HOME/AWAY de syncs viejos."""
    abbr = team_abbr_for_display(team.id, team.abbreviation, team.name)
    return TeamOut(id=team.id, name=team.name, abbreviation=abbr)
