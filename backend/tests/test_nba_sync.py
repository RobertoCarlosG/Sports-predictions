"""Tests de sync NBA con un cliente falso (SQLite en memoria)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.nba import NbaGame, NbaTeam
from app.services.nba_sync import sync_season


class _FakeNbaClient:
    def __init__(self, rows):
        self._rows = rows

    async def league_game_log(self, season, *, season_type=None):
        return self._rows


def _rows():
    def row(gid, tid, name, abbr, matchup, wl, pts):
        return {
            "GAME_ID": gid,
            "SEASON_ID": "22023",
            "TEAM_ID": tid,
            "TEAM_NAME": name,
            "TEAM_ABBREVIATION": abbr,
            "GAME_DATE": "2023-10-24",
            "MATCHUP": matchup,
            "WL": wl,
            "PTS": pts,
            "FGA": 88,
            "FTA": 20,
            "OREB": 10,
            "TOV": 13,
            "FGM": 40,
            "FG3M": 12,
        }

    return [
        row("0022300001", 1610612747, "Lakers", "LAL", "LAL vs. DEN", "L", 107),
        row("0022300001", 1610612743, "Nuggets", "DEN", "DEN @ LAL", "W", 119),
    ]


@pytest.mark.asyncio
async def test_sync_season_upserts_games_and_teams(sqlite_session_factory):
    client = _FakeNbaClient(_rows())
    async with sqlite_session_factory() as session:
        games = await sync_season(session, client, "2023-24")
        await session.commit()
        assert len(games) == 1
        n_games = (await session.execute(select(func.count()).select_from(NbaGame))).scalar()
        n_teams = (await session.execute(select(func.count()).select_from(NbaTeam))).scalar()
        assert n_games == 1
        assert n_teams == 2
        g = (await session.execute(select(NbaGame))).scalar_one()
        assert g.home_score == 107 and g.away_score == 119
        assert g.boxscore_json is not None and "home" in g.boxscore_json
        # Conferencia/división rellenada desde el mapa estático.
        lal = (await session.execute(select(NbaTeam).where(NbaTeam.id == 1610612747))).scalar_one()
        assert lal.conference == "West"


@pytest.mark.asyncio
async def test_sync_season_is_idempotent(sqlite_session_factory):
    client = _FakeNbaClient(_rows())
    async with sqlite_session_factory() as session:
        await sync_season(session, client, "2023-24")
        await session.commit()
        await sync_season(session, client, "2023-24")
        await session.commit()
        n_games = (await session.execute(select(func.count()).select_from(NbaGame))).scalar()
        assert n_games == 1
