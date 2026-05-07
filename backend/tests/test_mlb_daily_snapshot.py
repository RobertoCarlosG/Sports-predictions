"""Tests unitarios de ``app.services.mlb_daily_snapshot`` (sin red ni Postgres real)."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.mlb_daily_snapshot as snap


def _shim_dt(fixed_now: dt.datetime):
    """Reemplaza el módulo ``datetime`` del snapshot (evita parchear tipos inmutables)."""

    class DtNs:
        UTC = dt.UTC
        timedelta = dt.timedelta

        class datetime:
            @classmethod
            def now(cls, tz=None):
                return fixed_now

    return DtNs()


def test_seconds_until_next_utc_run_later_same_day(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = dt.datetime(2026, 7, 1, 1, 30, 0, tzinfo=dt.UTC)
    monkeypatch.setattr(snap, "dt", _shim_dt(fixed))
    sec = snap._seconds_until_next_utc_run(3, 0)
    assert sec == pytest.approx(90 * 60)


def test_seconds_until_next_utc_run_rolls_to_next_day(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = dt.datetime(2026, 7, 1, 5, 0, 0, tzinfo=dt.UTC)
    monkeypatch.setattr(snap, "dt", _shim_dt(fixed))
    sec = snap._seconds_until_next_utc_run(3, 0)
    assert sec == pytest.approx(22 * 3600)


@pytest.mark.asyncio
async def test_run_mlb_daily_snapshot_invokes_sync_twice_and_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_session_factory,
) -> None:
    monkeypatch.setattr(snap, "async_session_factory", sqlite_session_factory)

    sync_dates: list[str] = []

    async def fake_sync(session, mlb, date_str: str, *, fetch_details: bool = True) -> None:
        sync_dates.append(date_str)

    rebuild = AsyncMock(return_value=19)

    monkeypatch.setattr(snap, "sync_games_for_date", fake_sync)
    monkeypatch.setattr(snap, "rebuild_game_feature_snapshots", rebuild)

    fake_now = dt.datetime(2026, 8, 15, 12, 0, 0, tzinfo=dt.UTC)
    monkeypatch.setattr(snap, "dt", _shim_dt(fake_now))

    mock_http = MagicMock()
    result = await snap.run_mlb_daily_snapshot(mock_http)

    assert len(sync_dates) == 2
    assert sync_dates[0] == "2026-08-15"
    assert sync_dates[1] == "2026-08-16"
    assert result.season == "2026"
    assert result.snapshot_rows == 19
    assert rebuild.await_count == 1


@pytest.mark.asyncio
async def test_daily_snapshot_job_delegates() -> None:
    with patch.object(snap, "run_mlb_daily_snapshot", new_callable=AsyncMock) as run_job:
        await snap.run_mlb_daily_snapshot_job(MagicMock())
    run_job.assert_awaited_once()
