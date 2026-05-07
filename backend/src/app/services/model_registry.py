"""Registro de modelos cargados en memoria (tabla ``model_versions``).

Cada vez que el API carga un modelo nuevo (en ``lifespan`` al arrancar o vía
``POST /admin/model/reload``) registramos la metadata correspondiente. Una sola fila
puede ser ``is_active = True`` a la vez (asegurado por ``ux_model_versions_active`` en
SQL); el resto queda como histórico para auditoría y rollback consciente.

La metadata se lee del bundle ``joblib`` (clave ``training_meta`` que
``train_from_db`` serializa como JSON) y de ``stat()`` del archivo. No se hace red
ni operaciones costosas: si el bundle es viejo (sin ``training_meta``), se guarda
solo lo que se conoce.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path
from typing import Any

import joblib
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.predictor import MlbPredictionService
from app.models.mlb import ModelVersion

log = logging.getLogger(__name__)

_SYNTHETIC_PREFIX = "rf-synthetic"


def _is_synthetic_base_version(base_version: str) -> bool:
    return base_version.startswith(_SYNTHETIC_PREFIX)


def _read_training_meta(bundle: dict[str, Any]) -> dict[str, Any]:
    """``training_meta`` puede venir como str (JSON) o dict; bundles viejos no lo traen."""
    raw = bundle.get("training_meta")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            log.warning("training_meta no es JSON válido; se ignora.")
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _safe_iso_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _feature_names_json(meta: dict[str, Any], bundle: dict[str, Any]) -> str | None:
    names = meta.get("feature_names") or bundle.get("feature_names")
    if not isinstance(names, list):
        return None
    try:
        return json.dumps([str(x) for x in names])
    except (TypeError, ValueError):
        return None


async def record_model_load(
    session: AsyncSession,
    svc: MlbPredictionService,
    *,
    loaded_by: str | None = None,
    notes: str | None = None,
) -> ModelVersion:
    """Marca el modelo actual como activo y guarda metadata.

    Es idempotente: si ya existe una fila con el mismo ``model_version``, se reutiliza
    (se actualiza ``loaded_at`` / ``loaded_by`` / ``notes``) y se asegura que sea la
    única ``is_active``. Devuelve la fila resultante (todavía no commit).
    """
    bundle = svc._load()  # noqa: SLF001 — uso interno: carga si no estaba en memoria.
    model_version = str(bundle.get("model_version") or "rf-v0")
    base_version = str(bundle.get("model_base_version") or "rf-v0")
    meta = _read_training_meta(bundle)
    metrics = meta.get("metrics") if isinstance(meta.get("metrics"), dict) else {}

    file_mtime: dt.datetime | None = None
    file_size: int | None = None
    model_path: Path | None = getattr(svc, "_model_path", None)
    if model_path is not None and model_path.is_file():
        st = model_path.stat()
        file_mtime = dt.datetime.fromtimestamp(st.st_mtime, tz=dt.UTC)
        file_size = int(st.st_size)

    existing = await session.execute(
        select(ModelVersion).where(ModelVersion.model_version == model_version)
    )
    row = existing.scalar_one_or_none()

    now = dt.datetime.now(dt.UTC)

    if row is None:
        row = ModelVersion(
            model_version=model_version,
            base_version=base_version,
            loaded_at=now,
            file_mtime=file_mtime,
            file_size_bytes=file_size,
            is_synthetic=_is_synthetic_base_version(base_version),
            trained_on_games=_safe_int(meta.get("trained_on_games")),
            val_accuracy_home=_safe_float(metrics.get("val_accuracy_home")),
            val_mae_total_runs=_safe_float(metrics.get("val_mae_total_runs")),
            val_proba_home_std=_safe_float(metrics.get("val_proba_home_std")),
            split_mode=(str(meta.get("split_mode")) if meta.get("split_mode") else None),
            val_from_requested=_safe_iso_date(meta.get("val_from_requested")),
            feature_names_json=_feature_names_json(meta, bundle),
            loaded_by=loaded_by,
            notes=notes,
            is_active=False,  # se activa abajo, junto con la desactivación atómica del previo
        )
        session.add(row)
        await session.flush()
    else:
        row.loaded_at = now
        row.file_mtime = file_mtime
        row.file_size_bytes = file_size
        # is_synthetic depende solo de base_version; nunca cambia para una misma fila.
        row.loaded_by = loaded_by if loaded_by is not None else row.loaded_by
        if notes is not None:
            row.notes = notes
        # Métricas pueden actualizarse si el bundle se reentrenó con misma versión + nuevo mtime.
        row.trained_on_games = _safe_int(meta.get("trained_on_games")) or row.trained_on_games
        row.val_accuracy_home = (
            _safe_float(metrics.get("val_accuracy_home")) if metrics else row.val_accuracy_home
        )
        row.val_mae_total_runs = (
            _safe_float(metrics.get("val_mae_total_runs")) if metrics else row.val_mae_total_runs
        )
        row.val_proba_home_std = (
            _safe_float(metrics.get("val_proba_home_std")) if metrics else row.val_proba_home_std
        )

    # Desactivar otras filas y activar esta. UPDATE primero, luego flag local: el índice
    # parcial UNIQUE solo permite una fila TRUE simultáneamente.
    await session.execute(
        update(ModelVersion)
        .where(ModelVersion.id != row.id, ModelVersion.is_active.is_(True))
        .values(is_active=False)
    )
    row.is_active = True
    await session.flush()
    log.info(
        "model_versions: activo=%s (base=%s, synthetic=%s, by=%s)",
        row.model_version,
        row.base_version,
        row.is_synthetic,
        loaded_by or "auto",
    )
    return row


async def get_active_model_version(session: AsyncSession) -> ModelVersion | None:
    result = await session.execute(
        select(ModelVersion).where(ModelVersion.is_active.is_(True)).limit(1)
    )
    return result.scalar_one_or_none()


async def list_model_versions(
    session: AsyncSession, *, limit: int = 20, offset: int = 0
) -> list[ModelVersion]:
    result = await session.execute(
        select(ModelVersion).order_by(desc(ModelVersion.loaded_at)).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


def backup_model_file(model_path: Path) -> Path | None:
    """Crea una copia ``model.joblib.bak.<UTC ISO>`` antes de sobrescribir.

    No falla si el archivo no existe (primer arranque). Devuelve la ruta del backup
    creado, o ``None`` si no había qué respaldar.
    """
    if not model_path.is_file():
        return None
    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = model_path.with_name(f"{model_path.name}.bak.{ts}")
    try:
        # joblib.load + dump conserva el bundle; copiamos byte a byte para no requerir
        # entender el contenido si está corrupto.
        backup_path.write_bytes(model_path.read_bytes())
        log.info("model.joblib backup creado en %s", backup_path)
        return backup_path
    except OSError:
        log.warning("no se pudo crear backup de %s", model_path, exc_info=True)
        return None


def quick_inspect_bundle(model_path: Path) -> dict[str, Any]:
    """Lectura rápida del bundle sin cargar el servicio (para `/admin/model/inspect`)."""
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    bundle = dict(joblib.load(model_path))
    return {
        "model_version_in_bundle": bundle.get("model_version"),
        "feature_names": bundle.get("feature_names"),
        "training_meta": _read_training_meta(bundle),
    }
