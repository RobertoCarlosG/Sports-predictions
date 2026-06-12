from __future__ import annotations

from fastapi import APIRouter, Request

from app.ml.model_routing import DEFAULT_ML_MODEL, get_prediction_service_optional

router = APIRouter()


@router.get("/")
async def root(request: Request) -> dict[str, object]:
    """Evita 404 en probes que piden `/`; indica si el modelo ML está cargado (sin exponer secretos)."""
    loaded = get_prediction_service_optional(request) is not None
    ver = getattr(request.app.state, "active_model_version", "") or None
    return {
        "service": "sports-predictions-api",
        "docs": "/docs",
        "health": "/health",
        "model_loaded": loaded,
        "default_model": DEFAULT_ML_MODEL,
        "active_model_version": ver,
        "predict_hint": (
            f"Si model_loaded es false, despliega artifacts/model_{DEFAULT_ML_MODEL}.joblib "
            "(o configura ML_MODEL_PATH_XGB) y reinicia; o entrena con train_from_db."
        ),
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
