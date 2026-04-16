from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from starlette.responses import Response

from app.api.routes import games, health, predict
from app.core.config import settings
from app.core.cors_utils import cors_headers_for_request
from app.core.exception_handlers import (
    programming_error_handler,
    sqlalchemy_error_handler,
)
from app.db.session import engine
from app.ml.predictor import MlbPredictionService, ensure_model_exists, resolve_model_path


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    model_path = resolve_model_path(settings.ml_model_path)
    ensure_model_exists(model_path)
    app.state.prediction_service = MlbPredictionService(model_path)
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
    application.include_router(predict.router, prefix="/api/v1", tags=["predict"])

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
