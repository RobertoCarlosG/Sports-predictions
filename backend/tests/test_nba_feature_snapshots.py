"""Tests de cálculo de snapshots NBA (rolling, rest/b2b, labels)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from app.models.nba import NbaGame, NbaGameFeatureSnapshot, NbaTeam
from app.services.nba_feature_snapshots import rebuild_nba_game_feature_snapshots


def _stats(pts):
    return {"PTS": pts, "FGM": 40, "FGA": 88, "FG3M": 12, "FTA": 20, "OREB": 10, "TOV": 13}


async def _seed(session):
    for tid, abbr in [(1, "AAA"), (2, "BBB"), (3, "CCC")]:
        session.add(NbaTeam(id=tid, name=abbr, abbreviation=abbr))
    await session.flush()
    base = dt.date(2024, 1, 1)
    # team1 vs team2 over consecutive days to exercise rest/b2b + rolling
    games = [
        ("001", base, 1, 2, 110, 100),
        ("002", base + dt.timedelta(days=1), 1, 3, 105, 108),  # team1 back-to-back
        ("003", base + dt.timedelta(days=4), 2, 1, 99, 120),
    ]
    for gid, gd, h, a, hs, as_ in games:
        session.add(
            NbaGame(
                game_id=gid,
                season="2023-24",
                game_date=gd,
                status="Final",
                home_team_id=h,
                away_team_id=a,
                home_score=hs,
                away_score=as_,
                boxscore_json={"home": _stats(hs), "away": _stats(as_)},
            )
        )
    await session.flush()


@pytest.mark.asyncio
async def test_rebuild_computes_labels_and_rolling(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        await _seed(session)
        n = await rebuild_nba_game_feature_snapshots(session, rolling_window=10)
        await session.commit()
        assert n == 3

        snaps = {
            s.game_id: s
            for s in (await session.execute(select(NbaGameFeatureSnapshot))).scalars().all()
        }
        # Labels del primer partido (110-100 local gana).
        s1 = snaps["001"]
        assert s1.home_win == 1
        assert s1.margin == 10.0
        assert s1.total_points == 210.0
        # Primer partido: sin historial previo → rolling None (defaults se inyectan en features).
        assert s1.home_win_pct_roll is None

        # Tercer partido: team1 (visitante) ya jugó 2 → tiene rolling y rest.
        s3 = snaps["003"]
        assert s3.away_win_pct_roll is not None
        assert s3.away_rest_days is not None

        # Back-to-back de team1 en el 2º partido (local): rest=1, b2b=1.
        s2 = snaps["002"]
        assert s2.home_rest_days == 1
        assert s2.home_is_b2b == 1


@pytest.mark.asyncio
async def test_rebuild_skips_labels_for_non_final(sqlite_session_factory):
    async with sqlite_session_factory() as session:
        for tid, abbr in [(1, "AAA"), (2, "BBB")]:
            session.add(NbaTeam(id=tid, name=abbr, abbreviation=abbr))
        await session.flush()
        session.add(
            NbaGame(
                game_id="900",
                season="2023-24",
                game_date=dt.date(2024, 2, 1),
                status="Scheduled",
                home_team_id=1,
                away_team_id=2,
                home_score=None,
                away_score=None,
            )
        )
        await session.flush()
        await rebuild_nba_game_feature_snapshots(session, rolling_window=10)
        await session.commit()
        s = (await session.execute(select(NbaGameFeatureSnapshot))).scalar_one()
        assert s.home_win is None and s.margin is None and s.total_points is None
