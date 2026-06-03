"""Entrena un modelo (Random Forest o XGBoost) desde `game_feature_snapshots` + `games`.

Uso (desde `backend/`):

  # Random Forest (comportamiento por defecto)
  uv run python -m app.ml.train_from_db
  uv run python -m app.ml.train_from_db --val-from 2025-07-01 --season 2025

  # XGBoost
  uv run python -m app.ml.train_from_db --algorithm xgb
  uv run python -m app.ml.train_from_db --algorithm xgb --val-from 2025-07-01

  # Bayesian hyperparameter search (builds on prior runs via Optuna SQLite study)
  uv run python -m app.ml.train_from_db --bayesian
  uv run python -m app.ml.train_from_db --bayesian --bayesian-trials 50

  # Train + fit calibration layer on validation set
  uv run python -m app.ml.train_from_db --calibrate

Partición: filas con `game_date` < `--val-from` → train; `>= val-from` → validación.
Si no pasas `--val-from`, usa 80% temporal (primer 80% fechas train, resto val).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import accuracy_score, mean_absolute_error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.ml.features import FEATURE_NAMES, build_feature_values_for_training
from app.models.mlb import Game, GameFeatureSnapshot

log = logging.getLogger(__name__)


async def _load_xy(
    session: AsyncSession,
    *,
    season: str | None,
) -> tuple[NDArray[np.float64], NDArray[np.int_], NDArray[np.float64], list[dt.date]]:
    stmt = (
        select(GameFeatureSnapshot, Game)
        .join(Game, Game.game_pk == GameFeatureSnapshot.game_pk)
        .options(selectinload(Game.weather))
        .where(GameFeatureSnapshot.home_win.is_not(None))
        .where(GameFeatureSnapshot.total_runs.is_not(None))
        .order_by(Game.game_date, Game.game_pk)
    )
    if season is not None:
        stmt = stmt.where(Game.season == season)

    result = await session.execute(stmt)
    rows = result.all()
    if len(rows) < 20:
        raise RuntimeError(
            f"Need at least 20 labeled games for training; got {len(rows)}. "
            "Run backfill + rebuild_feature_snapshots first."
        )

    xs: list[list[float]] = []
    y_home: list[int] = []
    y_runs: list[float] = []
    dates: list[dt.date] = []
    for snap, game in rows:
        xs.append(
            build_feature_values_for_training(
                game,
                game.weather,
                snap,
            )
        )
        assert snap.home_win is not None and snap.total_runs is not None
        y_home.append(int(snap.home_win))
        y_runs.append(float(snap.total_runs))
        dates.append(game.game_date)

    x_arr = np.asarray(xs, dtype=np.float64)
    y_h = np.asarray(y_home, dtype=np.int_)
    y_r = np.asarray(y_runs, dtype=np.float64)
    _log_feature_health(x_arr)
    return x_arr, y_h, y_r, dates


def _log_feature_health(x: NDArray[np.float64]) -> None:
    """Si casi no hay varianza en X, el modelo tenderá a ~P(victoria local) constante (p. ej. ~48 %)."""
    x12 = x[:, :12] if x.shape[1] > 12 else x
    std = np.std(x12, axis=0)
    nz = np.count_nonzero(std > 1e-6)
    log.info(
        "features: rows=%d cols=%d (incl. defaults_injected) | cols 1-12: std>1e-6: %d/12 | mean std=%.4f",
        x.shape[0],
        x.shape[1],
        nz,
        float(np.mean(std)),
    )
    if nz < 4 or float(np.mean(std)) < 0.02:
        log.warning(
            "Las features están muy planas: revisa backfill + «recalcular indicadores» "
            "(game_feature_snapshots). Un modelo sintético (Gauss) parece más «disperso» "
            "pero no refleja datos reales."
        )


def _split_temporal(
    x: NDArray[np.float64],
    y_h: NDArray[np.int_],
    y_r: NDArray[np.float64],
    dates: list[dt.date],
    val_from: dt.date | None,
) -> tuple[NDArray, NDArray, NDArray, NDArray, NDArray, NDArray, str]:
    """Partición temporal. El último str es etiqueta para metadatos: ``val_from`` | ``80pct``."""
    if val_from is not None:
        mask_train = np.array([d < val_from for d in dates], dtype=bool)
        split_label = "val_from"
    else:
        n = len(dates)
        cut = int(n * 0.8)
        mask_train = np.zeros(n, dtype=bool)
        mask_train[:cut] = True
        split_label = "80pct"
    nt = int(mask_train.sum())
    nv = int((~mask_train).sum())
    if nt < 10 or nv < 5:
        raise RuntimeError(
            f"Partición inválida: train={nt}, val={nv} (se requiere train>=10 y val>=5). "
            f"val_from={val_from!s}. Deja vacío «validación desde» o elige una fecha con más "
            f"partidos anteriores (train) y al menos 5 posteriores (validación)."
        )
    return (
        x[mask_train],
        x[~mask_train],
        y_h[mask_train],
        y_h[~mask_train],
        y_r[mask_train],
        y_r[~mask_train],
        split_label,
    )


def _build_rf(args: argparse.Namespace) -> tuple[Any, Any]:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

    clf = RandomForestClassifier(
        n_estimators=args.trees,
        random_state=42,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
    )
    reg = RandomForestRegressor(
        n_estimators=args.trees,
        random_state=42,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
    )
    return clf, reg


def _build_xgb(args: argparse.Namespace) -> tuple[Any, Any]:
    from xgboost import XGBClassifier, XGBRegressor

    clf = XGBClassifier(
        n_estimators=args.trees,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        min_child_weight=args.min_child_weight,
        random_state=42,
        eval_metric="logloss",
    )
    reg = XGBRegressor(
        n_estimators=args.trees,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        subsample=args.subsample,
        colsample_bytree=args.colsample_bytree,
        min_child_weight=args.min_child_weight,
        random_state=42,
    )
    return clf, reg


async def _async_main(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        x, y_h, y_r, dates = await _load_xy(session, season=args.season)

    val_from = dt.date.fromisoformat(args.val_from) if args.val_from else None
    split_note: str
    try:
        x_tr, x_va, yh_tr, yh_va, yr_tr, yr_va, split_note = _split_temporal(
            x, y_h, y_r, dates, val_from
        )
    except RuntimeError as e:
        if val_from is not None:
            log.warning(
                "No se pudo usar val_from=%s (%s). Se aplica partición 80/20 temporal (orden de fechas).",
                val_from,
                e,
            )
            x_tr, x_va, yh_tr, yh_va, yr_tr, yr_va, split_note = _split_temporal(
                x, y_h, y_r, dates, None
            )
            split_note = "80pct_fallback_after_bad_val_from"
        else:
            raise
    log.info("split: %s | train=%d val=%d", split_note, len(yh_tr), len(yh_va))

    if getattr(args, "bayesian", False):
        from app.ml.bayesian_search import build_models_from_params, run_study

        log.info("Bayesian hyperparameter search enabled (n_trials=%d)", args.bayesian_trials)
        best_params = run_study(
            algorithm=args.algorithm,
            x_tr=x_tr,
            x_va=x_va,
            yh_tr=yh_tr,
            yh_va=yh_va,
            yr_tr=yr_tr,
            yr_va=yr_va,
            n_trials=args.bayesian_trials,
        )
        log.info("Using best Optuna params: %s", best_params)
        clf, reg = build_models_from_params(args.algorithm, best_params)
    elif args.algorithm == "xgb":
        clf, reg = _build_xgb(args)
        log.info(
            "XGBoost: trees=%d max_depth=%d lr=%.4f subsample=%.2f colsample=%.2f min_child_weight=%d",
            args.trees,
            args.max_depth,
            args.learning_rate,
            args.subsample,
            args.colsample_bytree,
            args.min_child_weight,
        )
    else:
        clf, reg = _build_rf(args)
        log.info(
            "RandomForest: trees=%d max_depth=%d min_samples_leaf=%d",
            args.trees,
            args.max_depth,
            args.min_samples_leaf,
        )

    clf.fit(x_tr, yh_tr)
    reg.fit(x_tr, yr_tr)

    pred_h = clf.predict(x_va)
    pred_r = reg.predict(x_va)
    acc = accuracy_score(yh_va, pred_h)
    mae = mean_absolute_error(yr_va, pred_r)
    log.info("validation accuracy (home win): %.4f", acc)
    log.info("validation MAE (total runs): %.4f", mae)
    proba_va = clf.predict_proba(x_va)
    val_proba_std: float | None = None
    if proba_va.shape[1] > 1:
        val_proba_std = float(np.std(proba_va[:, 1]))
        log.info(
            "validation P(home) std=%.4f (mayor => más dispersión entre partidos; "
            "cerca de 0 => casi misma prob. para todos)",
            val_proba_std,
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "algorithm": args.algorithm,
        "feature_names": FEATURE_NAMES,
        "trained_on_games": int(len(dates)),
        "val_from_requested": val_from.isoformat() if val_from else None,
        "split_mode": split_note,
        "metrics": {
            "val_accuracy_home": acc,
            "val_mae_total_runs": mae,
            "val_proba_home_std": val_proba_std,
        },
    }
    bundle = {
        "clf": clf,
        "reg": reg,
        "feature_names": FEATURE_NAMES,
        "model_version": args.model_version,
        "training_meta": json.dumps(meta),
    }
    joblib.dump(bundle, out)
    log.info("wrote %s  [algorithm=%s version=%s]", out.resolve(), args.algorithm, args.model_version)

    if getattr(args, "calibrate", False):
        from app.ml.calibration import fit_calibration_from_arrays, save_calibration

        log.info("Fitting calibration layer on validation set probabilities...")
        proba_va = clf.predict_proba(x_va)
        raw_probs = proba_va[:, 1] if proba_va.shape[1] > 1 else proba_va[:, 0]
        calibrator = fit_calibration_from_arrays(raw_probs, yh_va)
        cal_path = save_calibration(args.model_version, calibrator)
        log.info("calibration saved to %s", cal_path)


def main(argv: list[str] | None = None) -> None:
    # stdout: el panel admin muestra stdout_tail del subproceso (stderr se fusiona allí también).
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    p = argparse.ArgumentParser(
        description="Train RF or XGBoost from game_feature_snapshots (real labels)."
    )
    p.add_argument(
        "--algorithm",
        choices=["rf", "xgb"],
        default="rf",
        help="Algorithm: 'rf' = Random Forest (default), 'xgb' = XGBoost",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Output joblib path (default: artifacts/model.joblib for rf, artifacts/model_xgb.joblib for xgb)",
    )
    p.add_argument("--season", default=None, help="Restrict to season e.g. 2025")
    p.add_argument(
        "--val-from",
        default=None,
        help="YYYY-MM-DD: validation is games on or after this date",
    )
    p.add_argument("--trees", type=int, default=128, help="n_estimators")
    p.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Max tree depth (default: 16 for rf, 6 for xgb)",
    )
    p.add_argument(
        "--model-version",
        default=None,
        help="Version string returned by the predict API (default: rf-db-v1 or xgb-db-v1)",
    )
    # RF-specific
    p.add_argument(
        "--min-samples-leaf",
        type=int,
        default=2,
        help="[RF only] Minimum samples per leaf",
    )
    # XGB-specific
    p.add_argument("--learning-rate", type=float, default=0.05, help="[XGB only] Learning rate")
    p.add_argument("--subsample", type=float, default=0.8, help="[XGB only] Row subsampling ratio")
    p.add_argument(
        "--colsample-bytree", type=float, default=0.8, help="[XGB only] Column subsampling ratio"
    )
    p.add_argument(
        "--min-child-weight", type=int, default=3, help="[XGB only] Minimum child weight"
    )
    # Bayesian hyperparameter search
    p.add_argument(
        "--bayesian",
        action="store_true",
        help="Use Optuna Bayesian search to find best hyperparameters (persists study across runs)",
    )
    p.add_argument(
        "--bayesian-trials",
        type=int,
        default=30,
        help="Number of Optuna trials to run when --bayesian is set (default: 30)",
    )
    # Post-training calibration
    p.add_argument(
        "--calibrate",
        action="store_true",
        help="After training, fit a probability calibration layer on the validation set",
    )

    args = p.parse_args(argv)

    # Apply algorithm-specific defaults for args that weren't set explicitly.
    if args.max_depth is None:
        args.max_depth = 6 if args.algorithm == "xgb" else 16
    if args.output is None:
        args.output = (
            "src/app/ml/artifacts/model_xgb.joblib"
            if args.algorithm == "xgb"
            else "src/app/ml/artifacts/model.joblib"
        )
    if args.model_version is None:
        args.model_version = "xgb-db-v1" if args.algorithm == "xgb" else "rf-db-v1"

    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
