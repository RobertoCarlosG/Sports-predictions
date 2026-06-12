"""Selección del servicio de predicción (RF vs XGBoost) para rutas públicas y pipeline."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException, Request

from app.ml.predictor import MlbPredictionService

MlModelKind = Literal["rf", "xgb"]

# Modelo servido por defecto en /predict, /games?include_predictions=true y pipeline.
DEFAULT_ML_MODEL: MlModelKind = "xgb"


def _app_state(holder: Request | Any) -> Any:
    if hasattr(holder, "app"):
        return holder.app.state
    return holder.state


def _service_from_state(state: Any, model: MlModelKind) -> MlbPredictionService | None:
    if model == "xgb":
        return getattr(state, "prediction_service_xgb", None)
    return getattr(state, "prediction_service", None)


def get_prediction_service(
    holder: Request | Any,
    model: MlModelKind = DEFAULT_ML_MODEL,
) -> MlbPredictionService:
    svc = _service_from_state(_app_state(holder), model)
    if svc is not None:
        return svc
    if model == "xgb":
        raise HTTPException(
            status_code=503,
            detail=(
                "Modelo XGBoost no disponible. Entrena con --algorithm xgb, "
                "coloca el archivo en artifacts/model_xgb.joblib y reinicia el servicio."
            ),
        )
    raise HTTPException(
        status_code=503,
        detail=(
            "Modelo Random Forest no disponible. Entrena el modelo, configura ML_MODEL_PATH "
            "y usa administración para recargar, o reinicia el servicio."
        ),
    )


def get_prediction_service_optional(
    holder: Request | Any,
    model: MlModelKind = DEFAULT_ML_MODEL,
) -> MlbPredictionService | None:
    try:
        return get_prediction_service(holder, model)
    except HTTPException:
        return None


def sync_primary_model_version(
    holder: Request | Any,
    model: MlModelKind,
    svc: MlbPredictionService,
) -> None:
    """Actualiza ``active_model_version`` solo cuando se usa el modelo primario (por defecto)."""
    if model == DEFAULT_ML_MODEL:
        _app_state(holder).active_model_version = svc.model_version
