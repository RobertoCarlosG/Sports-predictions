from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from starlette.responses import Response

from app.api.routes import admin, games, health, mlb, predict
from app.core.config import settings
from app.core.cors_utils import cors_headers_for_request
from app.core.exception_handlers import (
    programming_error_handler,
    sqlalchemy_error_handler,
)
from app.db.session import engine
from app.ml.predictor import MlbPredictionService, ensure_model_exists, resolve_model_path
from app.services.admin_backfill_state import initial_backfill_job_state

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    app.state.backfill_job = initial_backfill_job_state()
    model_path = resolve_model_path(settings.ml_model_path)
    if not model_path.is_file() and settings.ml_auto_synthetic_on_missing:
        log.warning("ML model missing; training synthetic placeholder (ml_auto_synthetic_on_missing=true).")
        ensure_model_exists(model_path)

    if settings.admin_jwt_secret.strip():
        log.info("Panel Operaciones: ADMIN_JWT_SECRET está definido (longitud=%s).", len(settings.admin_jwt_secret))
    else:
        log.warning(
            "Panel Operaciones: ADMIN_JWT_SECRET vacío — /api/v1/admin/auth/login responderá 503 hasta configurarlo.",
        )

    if model_path.is_file():
        svc = MlbPredictionService(model_path)
        app.state.prediction_service = svc
        app.state.active_model_version = svc.model_version
        log.info("ML model loaded from %s version=%s", model_path, app.state.active_model_version)
    else:
        log.warning(
            "No ML model at %s — predict endpoints return 503 until you train and reload or restart.",
            model_path,
        )
        app.state.prediction_service = None
        app.state.active_model_version = ""

    yield
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
    application.include_router(games.router, prefix="/api/v1", tags=["games"])
    application.include_router(mlb.router, prefix="/api/v1", tags=["mlb"])
    application.include_router(predict.router, prefix="/api/v1", tags=["predict"])
    application.include_router(admin.router, prefix="/api/v1", tags=["admin"])

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
