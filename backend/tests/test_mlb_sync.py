import datetime as dt
from typing import Any

import pytest
from sqlalchemy import select

import app.services.mlb_sync as mlb_sync
from app.models.mlb import Game
from app.services.mlb_client import parse_schedule_games
from app.services.mlb_sync import lineups_from_boxscore, starters_from_boxscore


def test_lineups_from_boxscore_extracts_batters() -> None:
    box = {
        "teams": {
            "away": {
                "team": {"abbreviation": "AWY", "name": "Away Club"},
                "players": {
                    "ID111": {
                        "person": {"fullName": "Uno Away"},
                        "position": {"abbreviation": "CF"},
                        "jerseyNumber": "1",
                        "battingOrder": "101",
                    }
                },
                "batters": [111],
            },
            "home": {
                "team": {"abbreviation": "HOM"},
                "players": {
                    "ID222": {
                        "person": {"fullName": "Dos Home"},
                        "position": {"abbreviation": "2B"},
                    }
                },
                "batters": [222],
            },
        }
    }
    out = lineups_from_boxscore(box)
    assert out is not None
    assert out["source"] == "boxscore"
    assert out["away"]["team"] == "AWY"
    assert len(out["away"]["batters"]) == 1
    assert out["away"]["batters"][0]["name"] == "Uno Away"
    assert out["home"]["batters"][0]["name"] == "Dos Home"


def test_lineups_from_boxscore_returns_none_without_teams() -> None:
    assert lineups_from_boxscore({}) is None
    assert lineups_from_boxscore({"teams": {}}) is None


def test_starters_from_boxscore_first_pitchers() -> None:
    box = {
        "teams": {
            "home": {"pitchers": [123, 456]},
            "away": {"pitchers": [999]},
        }
    }
    h, a = starters_from_boxscore(box)
    assert h == 123
    assert a == 999


def test_starters_from_boxscore_empty() -> None:
    assert starters_from_boxscore({}) == (None, None)
    assert starters_from_boxscore({"teams": {"home": {}, "away": {}}}) == (None, None)


# ---------------------------------------------------------------------------
# Marcadores de partidos sin empezar y aplazados reprogramados (sync contra SQLite)
# ---------------------------------------------------------------------------

_PK = 849817


def _schedule(
    *,
    date: str,
    official: str,
    coded: str,
    abstract: str,
    detailed: str,
    home_score: int | None = None,
    away_score: int | None = None,
    reschedule: str | None = None,
    game_dt: str = "2026-10-18T21:08:00Z",
    game_type: str = "L",
    pk: int = _PK,
    home_team: dict[str, Any] | None = None,
) -> dict[str, Any]:
    g: dict[str, Any] = {
        "gamePk": pk,
        "gameType": game_type,
        "season": "2026",
        "gameDate": game_dt,
        "officialDate": official,
        "status": {"abstractGameState": abstract, "codedGameState": coded, "detailedState": detailed},
        "teams": {
            "home": {
                "team": home_team or {"id": 114, "name": "Cleveland Guardians", "abbreviation": "CLE"},
                "score": home_score,
            },
            "away": {"team": {"id": 139, "name": "Tampa Bay Rays", "abbreviation": "TB"}, "score": away_score},
        },
        "venue": {"id": 5, "name": "Progressive Field"},
    }
    if reschedule:
        g["rescheduleGameDate"] = reschedule
        g["rescheduleDate"] = f"{reschedule}T21:08:00Z"
    return {"dates": [{"date": date, "games": [g]}]}


_SCHEDULED = dict(official="2026-10-23", coded="S", abstract="Preview", detailed="Scheduled")
_STUB = dict(
    date="2026-10-16",
    official="2026-10-18",
    coded="D",
    abstract="Final",
    detailed="Postponed",
    reschedule="2026-10-18",
    game_dt="2026-10-17T00:00:00Z",
)
_MAKEUP = dict(date="2026-10-18", official="2026-10-18", coded="F", abstract="Final", detailed="Final")


class _FakeMlb:
    """Boxscore/linescore de un partido sin empezar: 0 carreras por lado (como statsapi)."""

    def __init__(self, by_date: dict[str, dict[str, Any]], by_pk: dict[str, Any] | None = None) -> None:
        self.by_date = by_date
        self.by_pk = by_pk
        self.linescore_calls = 0

    async def schedule(self, date_str: str) -> dict[str, Any]:
        return self.by_date[date_str]

    async def schedule_for_game(self, game_pk: int) -> dict[str, Any]:
        assert self.by_pk is not None
        return self.by_pk

    async def boxscore(self, game_pk: int) -> dict[str, Any]:
        side = {"teamStats": {"batting": {"runs": 0}}, "pitchers": []}
        return {"teams": {"home": side, "away": side}}

    async def live_feed(self, game_pk: int) -> dict[str, Any]:
        return {"gameData": {"status": "preview"}}

    async def linescore(self, game_pk: int) -> dict[str, Any]:
        self.linescore_calls += 1
        return {"teams": {"home": {"runs": 0}, "away": {"runs": 0}}}


@pytest.fixture(autouse=True)
def _no_pg_statement_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(session: Any) -> None:
        return None

    monkeypatch.setattr(mlb_sync, "_set_local_statement_timeout_for_mlb_write", _noop)


async def _sync(session_factory: Any, mlb: _FakeMlb, date: str) -> None:
    async with session_factory() as session:
        await mlb_sync.sync_games_for_date(session, mlb, date, fetch_details=True)  # type: ignore[arg-type]
        await session.commit()


async def _game(session_factory: Any) -> Game:
    async with session_factory() as session:
        return (await session.execute(select(Game).where(Game.game_pk == _PK))).scalar_one()


@pytest.mark.parametrize(
    ("item", "started"),
    [
        ({"coded_state": "S", "abstract_state": "Preview", "status": "Scheduled"}, False),
        ({"coded_state": "P", "abstract_state": "Preview", "status": "Pre-Game"}, False),
        ({"coded_state": "P", "abstract_state": "Live", "status": "Warmup"}, False),
        ({"coded_state": "D", "abstract_state": "Final", "status": "Postponed"}, False),
        ({"coded_state": "C", "abstract_state": "Final", "status": "Cancelled"}, False),
        ({"coded_state": "I", "abstract_state": "Live", "status": "In Progress"}, True),
        ({"coded_state": "F", "abstract_state": "Final", "status": "Final"}, True),
        ({"status": "Scheduled"}, False),  # payload sin estados codificados
        ({"status": "Final"}, True),
    ],
)
def test_schedule_item_has_started(item: dict[str, Any], started: bool) -> None:
    assert mlb_sync.schedule_item_has_started(item) is started


def test_parse_schedule_uses_official_date_and_reschedule() -> None:
    (stub,) = parse_schedule_games(_schedule(**_STUB))
    assert stub["game_date"] == "2026-10-18"
    assert stub["reschedule_date"] == "2026-10-18"
    assert stub["coded_state"] == "D"
    assert mlb_sync.is_rescheduled_stub(stub)
    (makeup,) = parse_schedule_games(_schedule(**_MAKEUP, home_score=1, away_score=3))
    assert makeup["reschedule_date"] is None
    assert not mlb_sync.is_rescheduled_stub(makeup)


@pytest.mark.asyncio
async def test_scheduled_game_stores_no_score(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    mlb = _FakeMlb({"2026-10-23": _schedule(date="2026-10-23", **_SCHEDULED)})
    await _sync(sqlite_session_factory, mlb, "2026-10-23")
    g = await _game(sqlite_session_factory)
    assert (g.home_score, g.away_score) == (None, None)
    assert g.status == "Scheduled"
    assert g.lineups_json == {"liveFeed": {"gameData": {"status": "preview"}}}  # alineación previa se conserva
    assert mlb.linescore_calls == 0


@pytest.mark.asyncio
async def test_resync_clears_stale_zero_zero(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    mlb = _FakeMlb({"2026-10-23": _schedule(date="2026-10-23", **_SCHEDULED)})
    await _sync(sqlite_session_factory, mlb, "2026-10-23")
    async with sqlite_session_factory() as session:
        row = (await session.execute(select(Game).where(Game.game_pk == _PK))).scalar_one()
        row.home_score, row.away_score = 0, 0  # fila guardada por la versión anterior
        await session.commit()
    await _sync(sqlite_session_factory, mlb, "2026-10-23")
    g = await _game(sqlite_session_factory)
    assert (g.home_score, g.away_score) == (None, None)


@pytest.mark.asyncio
async def test_final_game_keeps_schedule_scores(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    mlb = _FakeMlb({"2026-10-18": _schedule(**_MAKEUP, home_score=1, away_score=3)})
    await _sync(sqlite_session_factory, mlb, "2026-10-18")
    g = await _game(sqlite_session_factory)
    assert (g.home_score, g.away_score, g.status) == (1, 3, "Final")


@pytest.mark.asyncio
async def test_original_date_synced_after_makeup_keeps_final(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    mlb = _FakeMlb(
        {
            "2026-10-16": _schedule(**_STUB),
            "2026-10-18": _schedule(**_MAKEUP, home_score=1, away_score=3),
        }
    )
    await _sync(sqlite_session_factory, mlb, "2026-10-18")
    await _sync(sqlite_session_factory, mlb, "2026-10-16")
    g = await _game(sqlite_session_factory)
    assert g.game_date == dt.date(2026, 10, 18)
    assert (g.status, g.home_score, g.away_score) == ("Final", 1, 3)


@pytest.mark.asyncio
async def test_rescheduled_game_moves_to_makeup_date(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    original = _schedule(
        date="2026-10-16",
        official="2026-10-16",
        coded="S",
        abstract="Preview",
        detailed="Scheduled",
        game_dt="2026-10-17T00:00:00Z",
    )
    mlb = _FakeMlb({"2026-10-16": original})
    await _sync(sqlite_session_factory, mlb, "2026-10-16")
    assert (await _game(sqlite_session_factory)).game_date == dt.date(2026, 10, 16)

    # Se aplaza: la entrada del día original pasa a ser un «puntero» a la reposición.
    mlb.by_date["2026-10-16"] = _schedule(**_STUB)
    await _sync(sqlite_session_factory, mlb, "2026-10-16")
    g = await _game(sqlite_session_factory)
    assert g.game_date == dt.date(2026, 10, 18)
    assert g.game_datetime_utc is not None and g.game_datetime_utc.day == 18
    assert g.status == "Scheduled"  # el estado lo aporta la entrada real del día nuevo

    mlb.by_date["2026-10-18"] = _schedule(**_MAKEUP, home_score=1, away_score=3)
    await _sync(sqlite_session_factory, mlb, "2026-10-18")
    g = await _game(sqlite_session_factory)
    assert (g.game_date, g.status, g.home_score, g.away_score) == (dt.date(2026, 10, 18), "Final", 1, 3)


@pytest.mark.asyncio
async def test_sync_single_game_prefers_real_entry_over_stub(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    both = {
        "dates": _schedule(**_STUB)["dates"] + _schedule(**_MAKEUP, home_score=1, away_score=3)["dates"],
    }
    mlb = _FakeMlb({}, by_pk=both)
    async with sqlite_session_factory() as session:
        g = await mlb_sync.sync_single_game(session, mlb, _PK, fetch_details=True)  # type: ignore[arg-type]
        await session.commit()
    assert g is not None
    assert (g.game_date, g.status, g.home_score, g.away_score) == (dt.date(2026, 10, 18), "Final", 1, 3)


# ---------------------------------------------------------------------------
# Solo temporada regular + postemporada (sin pretemporada, exhibiciones ni All-Star)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("game_type", "tracked"),
    [("R", True), ("F", True), ("D", True), ("L", True), ("W", True), ("P", True)]
    + [("S", False), ("E", False), ("A", False), ("I", False), (None, True)],
)
def test_is_tracked_game_type(game_type: str | None, tracked: bool) -> None:
    assert mlb_sync.is_tracked_game_type({"game_type": game_type}) is tracked


def test_parse_schedule_exposes_game_type() -> None:
    (item,) = parse_schedule_games(_schedule(**_MAKEUP, game_type="S"))
    assert item["game_type"] == "S"


@pytest.mark.asyncio
async def test_sync_skips_spring_training_and_its_teams(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    from app.models.mlb import Team

    minor_league = {"id": 105, "name": "Sacramento River Cats", "abbreviation": "SAC"}
    spring = _schedule(
        **{**_MAKEUP, "date": "2026-03-20", "official": "2026-03-20"}, game_type="S", pk=1, home_team=minor_league
    )
    regular = _schedule(**{**_MAKEUP, "date": "2026-03-20", "official": "2026-03-20"}, game_type="R", pk=2)
    payload = {"dates": [{"date": "2026-03-20", "games": spring["dates"][0]["games"] + regular["dates"][0]["games"]}]}
    mlb = _FakeMlb({"2026-03-20": payload})
    await _sync(sqlite_session_factory, mlb, "2026-03-20")
    async with sqlite_session_factory() as session:
        pks = set((await session.execute(select(Game.game_pk))).scalars())
        team_ids = set((await session.execute(select(Team.id))).scalars())
    assert pks == {2}
    assert 105 not in team_ids
    assert {114, 139} <= team_ids


@pytest.mark.asyncio
async def test_sync_single_game_ignores_all_star(sqlite_session_factory) -> None:  # type: ignore[no-untyped-def]
    all_star = _schedule(**_MAKEUP, game_type="A", home_score=0, away_score=4)
    mlb = _FakeMlb({}, by_pk=all_star)
    async with sqlite_session_factory() as session:
        g = await mlb_sync.sync_single_game(session, mlb, _PK, fetch_details=True)  # type: ignore[arg-type]
        await session.commit()
        stored = (await session.execute(select(Game))).scalars().all()
    assert g is None
    assert stored == []
