from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from app.db.base import Base
from app.ml.predictor import MlbPredictionService
from app.models.mlb import ModelVersion
from app.services.model_registry import (
    backup_model_file,
    get_active_model_version,
    list_model_versions,
    record_model_load,
)


def _write_min_bundle(path: Path, *, base_version: str, with_meta: bool = True) -> None:
    """Crea un joblib con un bosque mínimo para que `MlbPredictionService` lo cargue."""
    rng = np.random.default_rng(0)
    n_features = 4
    x = rng.normal(size=(40, n_features))
    y_clf = (x[:, 0] + x[:, 1] > 0).astype(int)
    y_reg = x.sum(axis=1)
    clf = RandomForestClassifier(n_estimators=4, max_depth=3, random_state=0).fit(x, y_clf)
    reg = RandomForestRegressor(n_estimators=4, max_depth=3, random_state=0).fit(x, y_reg)

    bundle: dict[str, object] = {
        "clf": clf,
        "reg": reg,
        "model_version": base_version,
        "feature_names": [f"f{i}" for i in range(n_features)],
    }
    if with_meta:
        bundle["training_meta"] = json.dumps(
            {
                "trained_on_games": 100,
                "split_mode": "val_from",
                "val_from_requested": "2025-04-01",
                "feature_names": [f"f{i}" for i in range(n_features)],
                "metrics": {
                    "val_accuracy_home": 0.62,
                    "val_mae_total_runs": 1.85,
                    "val_proba_home_std": 0.07,
                },
            }
        )
    joblib.dump(bundle, path)


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_record_model_load_inserts_active_row(
    tmp_path: Path, session: AsyncSession
) -> None:
    p = tmp_path / "m.joblib"
    _write_min_bundle(p, base_version="rf-db-v1")
    svc = MlbPredictionService(p)

    row = await record_model_load(session, svc, loaded_by="alice", notes="test")

    assert row.is_active is True
    assert row.base_version == "rf-db-v1"
    assert row.model_version.startswith("rf-db-v1@")
    assert row.is_synthetic is False
    assert row.trained_on_games == 100
    assert row.val_accuracy_home == pytest.approx(0.62)
    assert row.val_mae_total_runs == pytest.approx(1.85)
    assert row.val_proba_home_std == pytest.approx(0.07)
    assert row.split_mode == "val_from"
    assert row.val_from_requested is not None
    assert row.val_from_requested.isoformat() == "2025-04-01"
    assert row.loaded_by == "alice"
    assert row.notes == "test"
    assert row.feature_names_json is not None
    assert json.loads(row.feature_names_json) == ["f0", "f1", "f2", "f3"]


async def test_synthetic_flag_detected_from_base_version(
    tmp_path: Path, session: AsyncSession
) -> None:
    p = tmp_path / "syn.joblib"
    _write_min_bundle(p, base_version="rf-synthetic-v0", with_meta=False)
    svc = MlbPredictionService(p)

    row = await record_model_load(session, svc)
    assert row.is_synthetic is True
    assert row.trained_on_games is None
    assert row.val_accuracy_home is None


async def test_only_one_active_row_after_two_loads(
    tmp_path: Path, session: AsyncSession
) -> None:
    p1 = tmp_path / "m1.joblib"
    p2 = tmp_path / "m2.joblib"
    _write_min_bundle(p1, base_version="rf-db-v1")
    _write_min_bundle(p2, base_version="rf-db-v2")
    svc1 = MlbPredictionService(p1)
    svc2 = MlbPredictionService(p2)

    row1 = await record_model_load(session, svc1, loaded_by="alice")
    row2 = await record_model_load(session, svc2, loaded_by="bob")

    assert row1.id != row2.id
    actives = (
        await session.execute(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    ).scalars().all()
    assert len(actives) == 1
    assert actives[0].id == row2.id

    fetched = await get_active_model_version(session)
    assert fetched is not None and fetched.id == row2.id


async def test_record_model_load_is_idempotent_for_same_version(
    tmp_path: Path, session: AsyncSession
) -> None:
    p = tmp_path / "m.joblib"
    _write_min_bundle(p, base_version="rf-db-v1")
    svc = MlbPredictionService(p)

    first = await record_model_load(session, svc, loaded_by="alice", notes="first")
    second = await record_model_load(session, svc, loaded_by="bob", notes="second")

    assert first.id == second.id
    assert second.loaded_by == "bob"
    assert second.notes == "second"
    rows = await list_model_versions(session)
    assert len(rows) == 1


async def test_list_model_versions_orders_by_loaded_at_desc(
    tmp_path: Path, session: AsyncSession
) -> None:
    p1 = tmp_path / "a.joblib"
    p2 = tmp_path / "b.joblib"
    _write_min_bundle(p1, base_version="rf-db-v1")
    _write_min_bundle(p2, base_version="rf-db-v2")
    await record_model_load(session, MlbPredictionService(p1))
    await record_model_load(session, MlbPredictionService(p2))

    rows = await list_model_versions(session, limit=10)
    assert [r.base_version for r in rows] == ["rf-db-v2", "rf-db-v1"]


def test_backup_model_file_creates_copy(tmp_path: Path) -> None:
    p = tmp_path / "model.joblib"
    p.write_bytes(b"hello")
    backup = backup_model_file(p)
    assert backup is not None and backup.exists()
    assert backup.read_bytes() == b"hello"
    assert backup.name.startswith("model.joblib.bak.")


def test_backup_model_file_returns_none_if_missing(tmp_path: Path) -> None:
    backup = backup_model_file(tmp_path / "nope.joblib")
    assert backup is None
