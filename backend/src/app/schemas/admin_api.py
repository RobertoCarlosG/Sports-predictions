from __future__ import annotations

from pydantic import BaseModel, Field


class AdminLoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AdminSessionResponse(BaseModel):
    """Perfil tras login; el JWT solo va en cookie HttpOnly."""

    username: str


class BackfillJobStatusResponse(BaseModel):
    """Estado de la última importación por fechas (panel Operaciones)."""

    status: str = "idle"
    job_id: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    date_start: str | None = None
    date_end: str | None = None
    days_total: int = 0
    days_done: int = 0
    current_date: str | None = None
    error_detail: str | None = None
    result_message: str | None = None


class AdminAuthReadyResponse(BaseModel):
    """Sin autenticación: JWT configurado y tabla admin_users accesible."""

    login_available: bool
    detail: str | None = None
    jwt_configured: bool = False
    admin_table_reachable: bool = False


class RebuildSnapshotsBody(BaseModel):
    season: str | None = None
    window: int = Field(default=10, ge=1, le=50)


class TrainModelBody(BaseModel):
    output: str | None = Field(
        default=None,
        description="Ruta del joblib; por defecto artifacts/model.joblib bajo el backend",
    )
    season: str | None = None
    val_from: str | None = Field(default=None, description="YYYY-MM-DD")
    model_version: str = "rf-db-v1"
    trees: int = Field(default=128, ge=10, le=500)


class BackfillBody(BaseModel):
    start: str = Field(description="YYYY-MM-DD")
    end: str = Field(description="YYYY-MM-DD")
    fetch_details: bool = True
    sleep_s: float = Field(default=0.0, ge=0.0, le=60.0)


class MessageResponse(BaseModel):
    message: str
    detail: str | None = None
    job_id: str | None = None


class TrainResultResponse(BaseModel):
    message: str
    stdout_tail: str | None = None
