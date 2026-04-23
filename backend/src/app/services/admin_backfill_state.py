"""Estado de la importación MLB por fechas (backfill) ejecutada en BackgroundTasks para la UI."""
from __future__ import annotations

import datetime as dt
import logging
import time
import traceback
import uuid
from typing import Any

from fastapi import FastAPI

from app.cli.backfill_history import _daterange, _run_backfill

log = logging.getLogger(__name__)


def initial_backfill_job_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "job_id": None,
        "started_at": None,
        "finished_at": None,
        "date_start": None,
        "date_end": None,
        "days_total": 0,
        "days_done": 0,
        "current_date": None,
        "error_detail": None,
        "result_message": None,
    }


def backfill_is_busy(app: FastAPI) -> bool:
    job = getattr(app.state, "backfill_job", None)
    return bool(job and job.get("status") in ("queued", "running"))


def prepare_backfill_job(app: FastAPI, start: dt.date, end: dt.date) -> str:
    """Registra la tarea antes de encolarla para que el cliente reciba job_id en la misma respuesta POST."""
    dates = _daterange(start, end)
    jid = str(uuid.uuid4())
    app.state.backfill_job = {
        **initial_backfill_job_state(),
        "status": "queued",
        "job_id": jid,
        "started_at": time.time(),
        "date_start": start.isoformat(),
        "date_end": end.isoformat(),
        "days_total": len(dates),
        "days_done": 0,
        "current_date": None,
    }
    return jid


async def run_tracked_backfill(
    app: FastAPI,
    start: dt.date,
    end: dt.date,
    *,
    fetch_details: bool,
    sleep_s: float,
    job_id: str,
) -> None:
    job = getattr(app.state, "backfill_job", None)
    if not job or job.get("job_id") != job_id:
        log.warning("backfill skip: job_id mismatch or missing state")
        return
    job["status"] = "running"

    async def progress(done: int, total: int, day_iso: str) -> None:
        j = getattr(app.state, "backfill_job", None)
        if j and j.get("job_id") == job_id:
            j["days_done"] = done
            j["days_total"] = total
            j["current_date"] = day_iso

    try:
        await _run_backfill(
            start,
            end,
            fetch_details=fetch_details,
            sleep_s=sleep_s,
            on_progress=progress,
        )
        j = getattr(app.state, "backfill_job", None)
        if j and j.get("job_id") == job_id:
            j["status"] = "success"
            j["finished_at"] = time.time()
            j["result_message"] = (
                f"Importación completada: {j.get('days_total', 0)} día(s) entre "
                f"{start.isoformat()} y {end.isoformat()}."
            )
            j["error_detail"] = None
    except Exception:
        j = getattr(app.state, "backfill_job", None)
        if j and j.get("job_id") == job_id:
            j["status"] = "error"
            j["finished_at"] = time.time()
            j["error_detail"] = traceback.format_exc()[-12000:]
            j["result_message"] = None
        log.exception("admin backfill background task failed")
