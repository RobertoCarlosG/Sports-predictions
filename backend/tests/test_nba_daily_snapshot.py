"""Tests unitarios de ``app.services.nba_daily_snapshot`` (sin red ni Postgres real)."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.nba_daily_snapshot as snap


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
    fixed = dt.datetime(2026, 1, 5, 1, 30, 0, tzinfo=dt.UTC)
    monkeypatch.setattr(snap, "dt", _shim_dt(fixed))
    sec = snap._seconds_until_next_utc_run(9, 0)
    assert sec == pytest.approx(7.5 * 3600)


def test_seconds_until_next_utc_run_rolls_to_next_day(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = dt.datetime(2026, 1, 5, 12, 0, 0, tzinfo=dt.UTC)
    monkeypatch.setattr(snap, "dt", _shim_dt(fixed))
    sec = snap._seconds_until_next_utc_run(9, 0)
    assert sec == pytest.approx(21 * 3600)


@pytest.mark.asyncio
async def test_run_nba_daily_snapshot_syncs_evaluates_and_rebuilds(
    monkeypatch: pytest.MonkeyPatch,
    sqlite_session_factory,
) -> None:
    monkeypatch.setattr(snap, "async_session_factory", sqlite_session_factory)
    monkeypatch.setattr(snap, "NbaApiClient", MagicMock())

    sync_dates: list[str] = []

    async def fake_sync(session, client, date_str: str):
        sync_dates.append(date_str)
        return []

    rebuild = AsyncMock(return_value=42)
    evaluate = AsyncMock()
    monkeypatch.setattr(snap, "sync_games_for_date", fake_sync)
    monkeypatch.setattr(snap, "rebuild_nba_game_feature_snapshots", rebuild)
    monkeypatch.setattr(snap, "evaluate_nba_predictions_for_final_games", evaluate)

    fake_now = dt.datetime(2026, 1, 5, 12, 0, 0, tzinfo=dt.UTC)
    monkeypatch.setattr(snap, "dt", _shim_dt(fake_now))

    result = await snap.run_nba_daily_snapshot()

    assert sync_dates == ["2026-01-05", "2026-01-06"]
    assert result.games_synced == 0
    assert result.snapshot_rows == 42
    assert rebuild.await_count == 1
    # Rebuild de TODOS los snapshots: las season strings en BD no son homogéneas.
    assert rebuild.await_args.kwargs["season"] is None
    # G4: la evaluación de aciertos se ejecuta exactamente una vez.
    assert evaluate.await_count == 1


@pytest.mark.asyncio
async def test_nba_daily_snapshot_job_delegates() -> None:
    with patch.object(snap, "run_nba_daily_snapshot", new_callable=AsyncMock) as run_job:
        await snap.run_nba_daily_snapshot_job()
    run_job.assert_awaited_once()
