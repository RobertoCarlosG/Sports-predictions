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
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_admin import AdminUserDep
from app.core.admin_security import create_access_token, hash_password
from app.core.config import settings
from app.db.session import get_db
from app.ml.predictor import MlbPredictionService, resolve_model_path
from app.models.mlb import AdminUser, Game, GamePredictionCache, Team
from app.schemas.admin_api import (
    AdminAuthReadyResponse,
    AdminLoginBody,
    AdminSessionResponse,
    BackfillBody,
    BackfillJobStatusResponse,
    MessageResponse,
    PredictionEvaluationItem,
    PredictionEvaluationsResponse,
    PredictionMetricsResponse,
    RebuildSnapshotsBody,
    TrainModelBody,
    TrainResultResponse,
)
from app.services.admin_auth import AdminAuthError, login_with_password
from app.services.admin_backfill_state import (
    backfill_is_busy,
    initial_backfill_job_state,
    prepare_backfill_job,
    run_tracked_backfill,
)
from app.services.feature_snapshots import rebuild_game_feature_snapshots
from app.services.mlb_client import MlbApiClient
from app.services.prediction_cache import clear_prediction_cache, evaluate_all_pending_predictions

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
async def admin_auth_ready(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdminAuthReadyResponse:
    """Público: JWT + tabla admin_users (el 503 en login suele ser uno de los dos, o ambos)."""
    jwt_ok = bool(settings.admin_jwt_secret.strip())
    table_ok = False
    table_hint: str | None = None
    try:
        await session.execute(select(AdminUser.id).limit(1))
        table_ok = True
    except ProgrammingError:
        table_hint = (
            "Falta la tabla admin_users. Ejecuta en PostgreSQL el script "
            "`backend/sql/002_prediction_cache_and_admin.sql` (misma base que DATABASE_URL). "
            "Sin eso, el login devuelve 503 (error de esquema)."
        )
    except SQLAlchemyError as e:
        log.warning("admin auth/ready DB check: %s", e)
        table_hint = "No se pudo consultar admin_users. Revisa DATABASE_URL y que el API use la misma BD que migraste."

    login_ok = jwt_ok and table_ok
    parts: list[str] = []
    if not jwt_ok:
        parts.append(
            "ADMIN_JWT_SECRET no está definido o está vacío en el proceso del API (Render → Environment). "
            "Nombre exacto: ADMIN_JWT_SECRET. Tras guardar, haz un deploy manual o «Restart» para recargar el servicio.",
        )
    if not table_ok and table_hint:
        parts.append(table_hint)
    detail = "\n\n".join(parts) if parts else None
    return AdminAuthReadyResponse(
        login_available=login_ok,
        detail=detail,
        jwt_configured=jwt_ok,
        admin_table_reachable=table_ok,
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
    request: Request,
    body: RebuildSnapshotsBody,
    _username: AdminUserDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    mlb = MlbApiClient(settings.mlb_api_base_url, request.app.state.http_client)
    n = await rebuild_game_feature_snapshots(
        session,
        rolling_window=body.window,
        season=body.season,
        mlb=mlb,
    )
    return MessageResponse(message=f"Indicadores recalculados para {n} partidos.", detail=None)


@router.post("/pipeline/clear-prediction-cache", response_model=MessageResponse)
async def admin_clear_prediction_cache(
    _username: AdminUserDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    n = await clear_prediction_cache(session)
    return MessageResponse(message="Caché de estimaciones vaciada.", detail=f"Filas eliminadas: {n}")


@router.post("/predictions/evaluate-pending", response_model=MessageResponse)
async def evaluate_pending_predictions(
    _username: AdminUserDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Evaluar todas las predicciones que tienen juegos finalizados pero aún no se han evaluado."""
    evaluated, correct = await evaluate_all_pending_predictions(session)
    await session.commit()
    
    if evaluated == 0:
        return MessageResponse(
            message="No hay predicciones pendientes de evaluación.",
            detail="Todas las predicciones con juegos finalizados ya han sido evaluadas.",
        )
    
    accuracy = round((correct / evaluated) * 100, 2) if evaluated > 0 else 0
    return MessageResponse(
        message=f"Se evaluaron {evaluated} predicciones.",
        detail=f"Correctas: {correct}, Incorrectas: {evaluated - correct}, Precisión: {accuracy}%",
    )


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
        "--max-depth",
        str(body.max_depth),
        "--min-samples-leaf",
        str(body.min_samples_leaf),
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
    out_txt = (proc.stdout or "").strip()
    err_txt = (proc.stderr or "").strip()
    combined = "\n".join(x for x in (out_txt, err_txt) if x)
    tail = combined[-4000:] if combined else ""
    if proc.returncode != 0:
        err = combined[-2000:] if combined else ""
        log.error("train failed: %s", err)
        raise HTTPException(
            status_code=400,
            detail="El entrenamiento falló. Revisa datos y logs del servidor.",
        )
    return TrainResultResponse(
        message="Entrenamiento completado. Usa «Recargar modelo» para activarlo sin reiniciar el API.",
        stdout_tail=tail or None,
    )


@router.get("/pipeline/backfill-status", response_model=BackfillJobStatusResponse)
async def admin_backfill_status(
    request: Request,
    _username: AdminUserDep,
) -> BackfillJobStatusResponse:
    job = getattr(request.app.state, "backfill_job", None) or initial_backfill_job_state()
    return BackfillJobStatusResponse.model_validate(job)


@router.post("/pipeline/backfill", response_model=MessageResponse)
async def admin_backfill(
    body: BackfillBody,
    background_tasks: BackgroundTasks,
    request: Request,
    _username: AdminUserDep,
) -> MessageResponse:
    if backfill_is_busy(request.app):
        raise HTTPException(
            status_code=409,
            detail="Ya hay una importación por fechas en curso (en cola o ejecutándose). Espera o revisa el progreso.",
        )
    start = dt.date.fromisoformat(body.start)
    end = dt.date.fromisoformat(body.end)
    jid = prepare_backfill_job(request.app, start, end)
    background_tasks.add_task(
        run_tracked_backfill,
        request.app,
        start,
        end,
        fetch_details=body.fetch_details,
        sleep_s=body.sleep_s,
        job_id=jid,
    )
    return MessageResponse(
        message="Importación por fechas iniciada en segundo plano.",
        detail=f"Rango: {body.start} — {body.end}.",
        job_id=jid,
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


@router.get("/predictions/metrics", response_model=PredictionMetricsResponse)
async def get_prediction_metrics(
    _username: AdminUserDep,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PredictionMetricsResponse:
    """Obtener métricas agregadas del sistema de predicciones."""
    total_predictions_result = await session.scalar(
        select(func.count()).select_from(GamePredictionCache)
    )
    total_predictions = total_predictions_result or 0
    
    total_evaluated_result = await session.scalar(
        select(func.count()).select_from(GamePredictionCache)
        .where(GamePredictionCache.evaluated_at.is_not(None))
    )
    total_evaluated = total_evaluated_result or 0
    
    total_correct_result = await session.scalar(
        select(func.count()).select_from(GamePredictionCache)
        .where(GamePredictionCache.is_correct == True)
    )
    total_correct = total_correct_result or 0
    
    total_incorrect_result = await session.scalar(
        select(func.count()).select_from(GamePredictionCache)
        .where(GamePredictionCache.is_correct == False)
    )
    total_incorrect = total_incorrect_result or 0
    
    pending_evaluation = total_predictions - total_evaluated
    
    accuracy_percentage = None
    if total_evaluated > 0:
        accuracy_percentage = round((total_correct / total_evaluated) * 100, 2)
    
    return PredictionMetricsResponse(
        total_predictions=total_predictions,
        total_evaluated=total_evaluated,
        total_correct=total_correct,
        total_incorrect=total_incorrect,
        accuracy_percentage=accuracy_percentage,
        pending_evaluation=pending_evaluation,
    )


@router.get("/predictions/evaluations", response_model=PredictionEvaluationsResponse)
async def get_prediction_evaluations(
    _username: AdminUserDep,
    session: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> PredictionEvaluationsResponse:
    """Obtener lista de predicciones evaluadas con detalles."""
    from sqlalchemy.orm import aliased, selectinload
    
    HomeTeam = aliased(Team)
    AwayTeam = aliased(Team)
    
    result = await session.execute(
        select(GamePredictionCache, Game, HomeTeam, AwayTeam)
        .join(Game, GamePredictionCache.game_pk == Game.game_pk)
        .join(HomeTeam, Game.home_team_id == HomeTeam.team_id)
        .join(AwayTeam, Game.away_team_id == AwayTeam.team_id)
        .where(GamePredictionCache.evaluated_at.is_not(None))
        .order_by(GamePredictionCache.evaluated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    rows = result.all()
    items = []
    
    for pred_cache, game, home_team, away_team in rows:
        items.append(
            PredictionEvaluationItem(
                game_pk=pred_cache.game_pk,
                game_date=game.game_date.isoformat(),
                home_team_name=home_team.display_name or "Home",
                away_team_name=away_team.display_name or "Away",
                predicted_winner=pred_cache.predicted_winner or "unknown",
                actual_winner=pred_cache.actual_winner or "unknown",
                is_correct=pred_cache.is_correct or False,
                home_win_probability=pred_cache.home_win_probability,
                home_score=game.home_score,
                away_score=game.away_score,
                evaluated_at=pred_cache.evaluated_at.isoformat() if pred_cache.evaluated_at else "",
            )
        )
    
    total_result = await session.scalar(
        select(func.count()).select_from(GamePredictionCache)
        .where(GamePredictionCache.evaluated_at.is_not(None))
    )
    total = total_result or 0
    
    return PredictionEvaluationsResponse(items=items, total=total)
