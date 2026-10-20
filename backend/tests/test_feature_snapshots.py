import datetime as dt

import pytest
from sqlalchemy import inspect, select

from app.models.mlb import Game, GameFeatureSnapshot, Team
from app.services.feature_snapshots import (
    _rolling_win_rate_and_runs,
    _should_persist_snapshot,
    game_has_final_scores,
    is_final_game_status,
    rebuild_game_feature_snapshots,
)


def test_is_final_game_status() -> None:
    assert is_final_game_status("Final")
    assert is_final_game_status("Game Over")
    assert not is_final_game_status("Preview")


def test_game_has_final_scores() -> None:
    g = Game(
        game_pk=1,
        season="2025",
        game_date=dt.date(2025, 4, 1),
        game_datetime_utc=None,
        status="Final",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=5,
        away_score=3,
        lineups_json=None,
        boxscore_json=None,
    )
    assert game_has_final_scores(g)


def test_rolling_win_rate_and_runs() -> None:
    w, r = _rolling_win_rate_and_runs([], 10)
    assert w == 0.5 and r == 4.5
    hist = [(True, 5), (False, 2), (True, 6)]
    w2, r2 = _rolling_win_rate_and_runs(hist, 10)
    assert w2 == 2 / 3
    assert abs(r2 - (5 + 2 + 6) / 3) < 1e-9


def test_should_persist_upcoming_snapshot_even_outside_requested_season() -> None:
    today = dt.date(2026, 4, 26)
    g = Game(
        game_pk=2,
        season="2026",
        game_date=today + dt.timedelta(days=1),
        game_datetime_utc=None,
        status="Scheduled",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=None,
        away_score=None,
        lineups_json=None,
        boxscore_json=None,
    )
    assert _should_persist_snapshot(g, season="2025", today=today, upcoming_snapshot_days=1)


def test_should_not_persist_non_upcoming_snapshot_outside_requested_season() -> None:
    today = dt.date(2026, 4, 26)
    g = Game(
        game_pk=3,
        season="2026",
        game_date=today + dt.timedelta(days=2),
        game_datetime_utc=None,
        status="Scheduled",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=None,
        away_score=None,
        lineups_json=None,
        boxscore_json=None,
    )
    assert not _should_persist_snapshot(g, season="2025", today=today, upcoming_snapshot_days=1)


def _make_game(game_pk: int, game_date: dt.date) -> Game:
    return Game(
        game_pk=game_pk,
        season="2025",
        game_date=game_date,
        game_datetime_utc=None,
        status="Final",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=5,
        away_score=3,
        lineups_json=None,
        boxscore_json=None,
    )


def test_should_persist_snapshot_within_date_range() -> None:
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    g = _make_game(10, dt.date(2025, 4, 15))
    assert _should_persist_snapshot(
        g, season=None, today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )


def test_should_not_persist_snapshot_before_date_range() -> None:
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    g = _make_game(11, dt.date(2025, 4, 5))
    assert not _should_persist_snapshot(
        g, season=None, today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )


def test_should_not_persist_snapshot_after_date_range() -> None:
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    g = _make_game(12, dt.date(2025, 4, 25))
    assert not _should_persist_snapshot(
        g, season=None, today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )


def test_date_range_takes_precedence_over_season() -> None:
    """start_date/end_date should override season-based filtering."""
    today = dt.date(2025, 4, 15)
    start = dt.date(2025, 4, 10)
    end = dt.date(2025, 4, 20)
    # Game is season 2024 (would normally be excluded by season="2025")
    g = Game(
        game_pk=13,
        season="2024",
        game_date=dt.date(2025, 4, 12),
        game_datetime_utc=None,
        status="Final",
        home_team_id=1,
        away_team_id=2,
        venue_id=None,
        venue_name=None,
        home_score=3,
        away_score=2,
        lineups_json=None,
        boxscore_json=None,
    )
    assert _should_persist_snapshot(
        g, season="2025", today=today, upcoming_snapshot_days=1, start_date=start, end_date=end
    )


def _snapshot_dict(rows: list[GameFeatureSnapshot]) -> dict[int, tuple]:
    return {
        s.game_pk: (
            s.home_wins_roll,
            s.away_wins_roll,
            s.home_runs_avg_roll,
            s.away_runs_avg_roll,
            s.home_win,
            s.total_runs,
            s.home_starter_era,
            s.away_starter_era,
            s.home_bullpen_era,
            s.away_bullpen_era,
        )
        for s in rows
    }


async def _seed_games(session) -> None:
    session.add_all(
        [
            Team(id=1, name="Home FC", abbreviation="HOM"),
            Team(id=2, name="Away FC", abbreviation="AWY"),
        ]
    )
    # Tres fechas, marcadores variados para que las rachas rodantes den valores != default.
    games = [
        (101, dt.date(2025, 4, 1), 5, 3),
        (102, dt.date(2025, 4, 2), 2, 6),
        (103, dt.date(2025, 4, 3), 4, 4),
        (104, dt.date(2025, 4, 3), 7, 1),
    ]
    for pk, gdate, hs, as_ in games:
        session.add(
            Game(
                game_pk=pk,
                season="2025",
                game_date=gdate,
                game_datetime_utc=None,
                status="Final",
                home_team_id=1,
                away_team_id=2,
                venue_id=None,
                venue_name=None,
                home_score=hs,
                away_score=as_,
                lineups_json={"big": "x" * 1000},
                boxscore_json=None,
            )
        )
    await session.commit()


@pytest.mark.asyncio
async def test_rebuild_streaming_matches_all_load(sqlite_session_factory) -> None:
    """low_memory=True (streaming, por defecto) debe producir snapshots idénticos a .all()."""
    async with sqlite_session_factory() as session:
        await _seed_games(session)

    async with sqlite_session_factory() as session:
        n_stream = await rebuild_game_feature_snapshots(session, season="2025", mlb=None, low_memory=True)
        await session.commit()
        streamed = _snapshot_dict(list((await session.execute(select(GameFeatureSnapshot))).scalars()))

    async with sqlite_session_factory() as session:
        n_all = await rebuild_game_feature_snapshots(session, season="2025", mlb=None, low_memory=False)
        await session.commit()
        loaded = _snapshot_dict(list((await session.execute(select(GameFeatureSnapshot))).scalars()))

    assert n_stream == n_all == 4
    assert streamed == loaded


@pytest.mark.asyncio
async def test_rebuild_defers_lineups_json(sqlite_session_factory) -> None:
    """El rebuild no debe materializar lineups_json (campo pesado, nunca usado)."""
    async with sqlite_session_factory() as session:
        await _seed_games(session)

    seen_loaded: list[bool] = []
    orig = rebuild_game_feature_snapshots

    async with sqlite_session_factory() as session:
        # Parcheamos _process_day para inspeccionar los objetos Game que llegan.
        import app.services.feature_snapshots as fs

        real_process = fs._process_day

        async def spy(session_, day_games, team_history, **kwargs):  # type: ignore[no-untyped-def]
            for g in day_games:
                unloaded = inspect(g).unloaded
                seen_loaded.append("lineups_json" in unloaded)
            return await real_process(session_, day_games, team_history, **kwargs)

        fs._process_day = spy  # type: ignore[assignment]
        try:
            await orig(session, season="2025", mlb=None, low_memory=False)
        finally:
            fs._process_day = real_process

    # Para cada juego, lineups_json debe seguir sin cargar (diferido).
    assert seen_loaded and all(seen_loaded)


@pytest.mark.asyncio
@pytest.mark.parametrize("low_memory", [True, False])
async def test_rebuild_uses_era_memo_and_box_starters(sqlite_session_factory, sqlite_engine, low_memory) -> None:
    """ERA desde `pitching_era_cache` precargado (sin SELECT por partido) y abridores del boxscore
    solo cuando faltan los ids — sin materializar `boxscore_json` en los objetos Game."""
    from sqlalchemy import event

    from app.models.mlb import PitchingEraCache

    async with sqlite_session_factory() as session:
        session.add_all(
            [Team(id=1, name="Home FC", abbreviation="HOM"), Team(id=2, name="Away FC", abbreviation="AWY")]
        )
        box = {"teams": {"home": {"pitchers": [501]}, "away": {"pitchers": [502]}}}
        for pk, gdate, starters in [
            (201, dt.date(2025, 4, 1), (None, None)),  # abridores solo en el boxscore
            (202, dt.date(2025, 4, 2), (601, 602)),  # abridores en la fila
        ]:
            session.add(
                Game(
                    game_pk=pk,
                    season="2025",
                    game_date=gdate,
                    status="Final",
                    home_team_id=1,
                    away_team_id=2,
                    home_score=3,
                    away_score=2,
                    boxscore_json=box,
                    home_starter_id=starters[0],
                    away_starter_id=starters[1],
                )
            )
        now = dt.datetime(2025, 4, 1, tzinfo=dt.UTC)
        for kind, ref_id, era in [("P", 501, 2.5), ("P", 502, 3.5), ("P", 601, 1.5), ("P", 602, 5.5)]:
            session.add(PitchingEraCache(kind=kind, ref_id=ref_id, season="2025", era=era, updated_at=now))
        for team_id, era in [(1, 3.9), (2, 4.1)]:
            session.add(PitchingEraCache(kind="T", ref_id=team_id, season="2025", era=era, updated_at=now))
        await session.commit()

    era_selects: list[str] = []

    def _count(conn, cursor, statement, *args):  # type: ignore[no-untyped-def]
        if statement.lstrip().upper().startswith("SELECT") and "pitching_era_cache" in statement:
            era_selects.append(statement)

    import app.services.feature_snapshots as fs

    loaded_box: list[bool] = []
    real_process = fs._process_day

    async def spy(session_, day_games, team_history, **kwargs):  # type: ignore[no-untyped-def]
        loaded_box.extend("boxscore_json" not in inspect(g).unloaded for g in day_games)
        return await real_process(session_, day_games, team_history, **kwargs)

    event.listen(sqlite_engine.sync_engine, "before_cursor_execute", _count)
    fs._process_day = spy  # type: ignore[assignment]
    try:
        async with sqlite_session_factory() as session:
            n = await rebuild_game_feature_snapshots(session, season="2025", mlb=None, low_memory=low_memory)
            await session.commit()
            snaps = {s.game_pk: s for s in (await session.execute(select(GameFeatureSnapshot))).scalars()}
    finally:
        fs._process_day = real_process
        event.remove(sqlite_engine.sync_engine, "before_cursor_execute", _count)

    assert n == 2
    assert len(era_selects) == 1  # una precarga, no 4 por partido
    assert loaded_box and not any(loaded_box)
    assert (snaps[201].home_starter_era, snaps[201].away_starter_era) == (2.5, 3.5)
    assert (snaps[202].home_starter_era, snaps[202].away_starter_era) == (1.5, 5.5)
    assert (snaps[202].home_bullpen_era, snaps[202].away_bullpen_era) == (3.9, 4.1)
