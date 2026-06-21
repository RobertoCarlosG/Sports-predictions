import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from starlette.responses import Response

from app.api.routes import admin, bets, features, games, health, mlb, model, nba, predict, user_auth
from app.core.config import settings
from app.core.cors_utils import cors_headers_for_request
from app.core.exception_handlers import (
    programming_error_handler,
    sqlalchemy_error_handler,
)
from app.db.session import async_session_factory, engine
from app.ml.model_routing import DEFAULT_ML_MODEL, get_prediction_service_optional
from app.ml.nba_predictor import NbaPredictionService
from app.ml.predictor import MlbPredictionService, ensure_model_exists, resolve_model_path
from app.services.admin_backfill_state import initial_backfill_job_state
from app.services.mlb_daily_snapshot import daily_snapshot_loop_forever
from app.services.model_registry import record_model_load

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Límites explícitos evitan abrir demasiados sockets simultáneos
    # (en macOS puede aparecer Errno 49).
    app.state.http_client = httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
    )
    # Evita GET /games duplicados (misma fecha/flags) ejecutando dos syncs MLB en paralelo.
    app.state.games_list_inflight = {}
    app.state.backfill_job = initial_backfill_job_state()
    model_path = resolve_model_path(settings.ml_model_path)
    if not model_path.is_file() and settings.ml_auto_synthetic_on_missing:
        log.warning(
            "ML model missing; training synthetic placeholder (ml_auto_synthetic_on_missing=true)."
        )
        ensure_model_exists(model_path)

    if settings.admin_jwt_secret.strip():
        log.info(
            "Panel Operaciones: ADMIN_JWT_SECRET está definido (longitud=%s).",
            len(settings.admin_jwt_secret),
        )
    else:
        log.warning(
            "Panel Operaciones: ADMIN_JWT_SECRET vacío — "
            "/api/v1/admin/auth/login responderá 503 hasta configurarlo.",
        )

    app.state.prediction_service = None
    app.state.prediction_service_xgb = None
    app.state.active_model_version = ""

    if model_path.is_file():
        app.state.prediction_service = MlbPredictionService(model_path)
        log.info(
            "Random Forest loaded from %s version=%s",
            model_path,
            app.state.prediction_service.model_version,
        )
    else:
        log.info("No Random Forest model at %s — ?model=rf will return 503.", model_path)

    xgb_path = resolve_model_path(settings.ml_model_path_xgb, default_name="model_xgb.joblib")
    if xgb_path.is_file():
        app.state.prediction_service_xgb = MlbPredictionService(xgb_path)
        log.info(
            "XGBoost loaded from %s version=%s",
            xgb_path,
            app.state.prediction_service_xgb.model_version,
        )
    else:
        log.info("No XGBoost model at %s — default predict/games need this file.", xgb_path)

    # --- Modelos NBA (xgb / lgbm / catboost) ---
    app.state.nba_prediction_service_xgb = None
    app.state.nba_prediction_service_lgbm = None
    app.state.nba_prediction_service_catboost = None
    _nba_specs = [
        ("nba_prediction_service_xgb", settings.ml_model_path_nba_xgb, "model_nba_xgb.joblib"),
        ("nba_prediction_service_lgbm", settings.ml_model_path_nba_lgbm, "model_nba_lgbm.joblib"),
        (
            "nba_prediction_service_catboost",
            settings.ml_model_path_nba_catboost,
            "model_nba_catboost.joblib",
        ),
    ]
    for attr, env_path, default_name in _nba_specs:
        path = resolve_model_path(env_path, default_name=default_name)
        if path.is_file():
            svc = NbaPredictionService(path)
            setattr(app.state, attr, svc)
            log.info("NBA model loaded from %s version=%s", path, svc.model_version)
        else:
            log.info("No NBA model at %s — /nba/predict para ese algoritmo dará 503.", path)

    primary_svc = get_prediction_service_optional(app)
    if primary_svc is not None:
        app.state.active_model_version = primary_svc.model_version
        log.info(
            "Primary ML model (%s) active version=%s",
            DEFAULT_ML_MODEL,
            app.state.active_model_version,
        )
        try:
            async with async_session_factory() as session:
                await record_model_load(
                    session,
                    primary_svc,
                    loaded_by=None,
                    notes=f"lifespan startup (default={DEFAULT_ML_MODEL})",
                )
                await session.commit()
        except Exception:
            log.warning(
                "model_versions: no se pudo registrar la carga inicial (¿migración 006 aplicada?).",
                exc_info=True,
            )
    else:
        log.warning(
            "No primary ML model (%s) loaded — predict/games return 503 "
            "until you deploy artifacts.",
            DEFAULT_ML_MODEL,
        )

    if settings.mlb_daily_snapshot_enabled:
        app.state.mlb_daily_snapshot_task = asyncio.create_task(
            daily_snapshot_loop_forever(app.state.http_client),
        )
        log.info(
            "Tarea MLB daily snapshot activa (UTC %02d:%02d).",
            settings.mlb_daily_snapshot_utc_hour,
            settings.mlb_daily_snapshot_utc_minute,
        )

    yield

    t = getattr(app.state, "mlb_daily_snapshot_task", None)
    if t is not None:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t
    await app.state.http_client.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Sports Predictions API",
        version="0.1.0",
        lifespan=lifespan,
    )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:4200"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health.router, tags=["health"])
    application.include_router(features.router, prefix="/api/v1", tags=["features"])
    application.include_router(games.router, prefix="/api/v1", tags=["games"])
    application.include_router(mlb.router, prefix="/api/v1", tags=["mlb"])
    application.include_router(nba.router, prefix="/api/v1", tags=["nba"])
    application.include_router(predict.router, prefix="/api/v1", tags=["predict"])
    application.include_router(model.router, prefix="/api/v1", tags=["model"])
    application.include_router(admin.router, prefix="/api/v1", tags=["admin"])
    application.include_router(user_auth.router, prefix="/api/v1")
    application.include_router(bets.router, prefix="/api/v1")

    application.add_exception_handler(ProgrammingError, programming_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)  # type: ignore[arg-type]

    async def http_exc_with_cors(request: Request, exc: HTTPException) -> Response:
        from fastapi.exception_handlers import http_exception_handler

        response = await http_exception_handler(request, exc)
        for k, v in cors_headers_for_request(request, settings.cors_origins).items():
            response.headers[k] = v
        return response

    async def validation_exc_with_cors(request: Request, exc: RequestValidationError) -> Response:
        from fastapi.exception_handlers import request_validation_exception_handler

        response = await request_validation_exception_handler(request, exc)
        for k, v in cors_headers_for_request(request, settings.cors_origins).items():
            response.headers[k] = v
        return response

    application.add_exception_handler(HTTPException, http_exc_with_cors)  # type: ignore[arg-type]
    application.add_exception_handler(RequestValidationError, validation_exc_with_cors)  # type: ignore[arg-type]
    return application


app = create_app()
