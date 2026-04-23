from __future__ import annotations

import datetime as dt
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import joblib
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_admin import AdminUserDep
from app.cli.backfill_history import _run_backfill
from app.core.admin_security import create_access_token, hash_password
from app.core.config import settings
from app.db.session import get_db
from app.ml.predictor import MlbPredictionService, resolve_model_path
from app.models.mlb import AdminUser
from app.schemas.admin_api import (
    AdminAuthReadyResponse,
    AdminLoginBody,
    AdminSessionResponse,
    BackfillBody,
    MessageResponse,
    RebuildSnapshotsBody,
    TrainModelBody,
    TrainResultResponse,
)
from app.services.admin_auth import AdminAuthError, login_with_password
from app.services.feature_snapshots import rebuild_game_feature_snapshots
from app.services.prediction_cache import clear_prediction_cache

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

BACKEND_ROOT = Path(__file__).resolve().parents[4]


def _set_admin_session_cookie(response: Response, token: str) -> None:
    kwargs: dict = {
        "key": settings.admin_cookie_name,
        "value": token,
        "httponly": True,
        "secure": settings.admin_cookie_secure,
        "samesite": settings.admin_cookie_samesite,
        "max_age": settings.admin_token_expire_minutes * 60,
        "path": "/",
    }
    if settings.admin_cookie_domain:
        kwargs["domain"] = settings.admin_cookie_domain
    response.set_cookie(**kwargs)


def _clear_admin_session_cookie(response: Response) -> None:
    kwargs: dict = {
        "key": settings.admin_cookie_name,
        "path": "/",
        "httponly": True,
        "secure": settings.admin_cookie_secure,
        "samesite": settings.admin_cookie_samesite,
    }
    if settings.admin_cookie_domain:
        kwargs["domain"] = settings.admin_cookie_domain
    response.delete_cookie(**kwargs)


@router.get("/auth/ready", response_model=AdminAuthReadyResponse)
async def admin_auth_ready() -> AdminAuthReadyResponse:
    """Público: comprueba si el servidor puede emitir sesiones del panel (evita 503 opacos en login)."""
    ok = bool(settings.admin_jwt_secret.strip())
    return AdminAuthReadyResponse(
        login_available=ok,
        detail=None
        if ok
        else "Falta ADMIN_JWT_SECRET en el servidor (p. ej. Render). Sin eso, login y /auth/me responden 503.",
    )


@router.post("/auth/bootstrap", response_model=AdminSessionResponse)
async def admin_bootstrap_first_user(
    response: Response,
    body: AdminLoginBody,
    session: Annotated[AsyncSession, Depends(get_db)],
    x_admin_bootstrap_secret: Annotated[str | None, Header(alias="X-Admin-Bootstrap-Secret")] = None,
) -> AdminSessionResponse:
    """
    Crea el **primer** (y solo el primer) usuario en `admin_users` cuando la tabla está vacía.
    Requiere `ADMIN_BOOTSTRAP_SECRET` en el servidor y el mismo valor en el header.
    Desactivar el secreto en .env tras usar; para más usuarios usar `python -m app.cli.create_admin`.
    """
    expected = settings.admin_bootstrap_secret.strip()
    if not expected:
        raise HTTPException(status_code=404, detail="No encontrado.")
    if not x_admin_bootstrap_secret or x_admin_bootstrap_secret.strip() != expected:
        raise HTTPException(status_code=403, detail="No autorizado.")
    if not settings.admin_jwt_secret.strip():
        raise HTTPException(status_code=503, detail="Servidor sin ADMIN_JWT_SECRET; no se puede crear sesión.")
    cnt = await session.scalar(select(func.count()).select_from(AdminUser))
    if (cnt or 0) > 0:
        raise HTTPException(
            status_code=403,
            detail="Ya existen operadores. Inicia sesión o usa create_admin para añadir más.",
        )
    dup = await session.execute(select(AdminUser).where(AdminUser.username == body.username))
    if dup.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Ese nombre de usuario ya existe.")
    session.add(
        AdminUser(
            username=body.username,
            password_hash=hash_password(body.password),
            is_active=True,
        )
    )
    await session.commit()
    token = create_access_token(
        secret=settings.admin_jwt_secret,
        subject=body.username,
        expire_minutes=settings.admin_token_expire_minutes,
    )
    _set_admin_session_cookie(response, token)
    log.warning("Primer usuario operaciones creado vía bootstrap (usuario=%s).", body.username)
    return AdminSessionResponse(username=body.username)


@router.post("/auth/login", response_model=AdminSessionResponse)
async def admin_login(
    response: Response,
    body: AdminLoginBody,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminSessionResponse:
    try:
        username, token = await login_with_password(body.username, body.password, session)
    except AdminAuthError as e:
        msg = str(e)
        code = 503 if "ADMIN_JWT_SECRET" in msg else 401
        raise HTTPException(status_code=code, detail=msg if code == 503 else "Usuario o contraseña incorrectos.") from e
    _set_admin_session_cookie(response, token)
    return AdminSessionResponse(username=username)


@router.post("/auth/logout", response_model=MessageResponse)
async def admin_logout(response: Response) -> MessageResponse:
    _clear_admin_session_cookie(response)
    return MessageResponse(message="Sesión cerrada.", detail=None)


@router.get("/auth/me", response_model=AdminSessionResponse)
async def admin_me(username: AdminUserDep) -> AdminSessionResponse:
    return AdminSessionResponse(username=username)


@router.post("/pipeline/rebuild-snapshots", response_model=MessageResponse)
async def admin_rebuild_snapshots(
    body: RebuildSnapshotsBody,
    _username: AdminUserDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    n = await rebuild_game_feature_snapshots(
        session, rolling_window=body.window, season=body.season
    )
    return MessageResponse(message=f"Indicadores recalculados para {n} partidos.", detail=None)


@router.post("/pipeline/clear-prediction-cache", response_model=MessageResponse)
async def admin_clear_prediction_cache(
    _username: AdminUserDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    n = await clear_prediction_cache(session)
    return MessageResponse(message="Caché de estimaciones vaciada.", detail=f"Filas eliminadas: {n}")


@router.post("/model/reload", response_model=MessageResponse)
async def admin_reload_model(request: Request, _username: AdminUserDep) -> MessageResponse:
    path = resolve_model_path(settings.ml_model_path)
    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail="No hay archivo de modelo en la ruta configurada.",
        )
    bundle = joblib.load(path)
    ver = str(bundle.get("model_version", "rf-v0"))
    request.app.state.active_model_version = ver
    request.app.state.prediction_service = MlbPredictionService(path)
    return MessageResponse(
        message="Modelo recargado en memoria.",
        detail=f"Versión: {ver}",
    )


@router.post("/pipeline/train", response_model=TrainResultResponse)
async def admin_train_model(
    body: TrainModelBody,
    _username: AdminUserDep,
) -> TrainResultResponse:
    out = body.output or str(BACKEND_ROOT / "src/app/ml/artifacts/model.joblib")
    cmd = [
        sys.executable,
        "-m",
        "app.ml.train_from_db",
        "--output",
        out,
        "--model-version",
        body.model_version,
        "--trees",
        str(body.trees),
    ]
    if body.season:
        cmd.extend(["--season", body.season])
    if body.val_from:
        cmd.extend(["--val-from", body.val_from])
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BACKEND_ROOT),
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Entrenamiento excedió el tiempo máximo.") from None
    tail = (proc.stdout or "")[-4000:]
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-2000:]
        log.error("train failed: %s", err)
        raise HTTPException(
            status_code=400,
            detail="El entrenamiento falló. Revisa datos y logs del servidor.",
        )
    return TrainResultResponse(
        message="Entrenamiento completado. Usa «Recargar modelo» para activarlo sin reiniciar el API.",
        stdout_tail=tail or None,
    )


@router.post("/pipeline/backfill", response_model=MessageResponse)
async def admin_backfill(
    body: BackfillBody,
    background_tasks: BackgroundTasks,
    _username: AdminUserDep,
) -> MessageResponse:
    start = dt.date.fromisoformat(body.start)
    end = dt.date.fromisoformat(body.end)
    background_tasks.add_task(
        _run_backfill,
        start,
        end,
        fetch_details=body.fetch_details,
        sleep_s=body.sleep_s,
    )
    return MessageResponse(
        message="Importación por fechas iniciada en segundo plano.",
        detail="Puede tardar varios minutos. Revisa los logs del servidor.",
    )


@router.get("/status", response_model=MessageResponse)
async def admin_status(request: Request, _username: AdminUserDep) -> MessageResponse:
    path = resolve_model_path(settings.ml_model_path)
    loaded = getattr(request.app.state, "prediction_service", None) is not None
    ver = getattr(request.app.state, "active_model_version", "") or "—"
    disk = path.is_file()
    detail = (
        f"Archivo en disco: {'sí' if disk else 'no'}. "
        f"Cargado en memoria: {'sí' if loaded else 'no'}. Versión activa: {ver}"
    )
    return MessageResponse(message="Estado del motor de estimación", detail=detail)
