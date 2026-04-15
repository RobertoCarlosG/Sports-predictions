from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import games, health, predict
from app.core.config import settings
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
    return application


app = create_app()
