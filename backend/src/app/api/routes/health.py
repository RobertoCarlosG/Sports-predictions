from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
async def root(request: Request) -> dict[str, object]:
    """Evita 404 en probes que piden `/`; indica si el modelo ML está cargado (sin exponer secretos)."""
    loaded = getattr(request.app.state, "prediction_service", None) is not None
    ver = getattr(request.app.state, "active_model_version", "") or None
    return {
        "service": "sports-predictions-api",
        "docs": "/docs",
        "health": "/health",
        "model_loaded": loaded,
        "active_model_version": ver,
        "predict_hint": (
            "Si model_loaded es false, configura ML_MODEL_PATH con un .joblib existente y reinicia; "
            "o entrena (train_from_db) y despliega el artefacto."
        ),
    }


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
