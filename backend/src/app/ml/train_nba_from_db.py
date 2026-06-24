"""Entrena modelos NBA (XGBoost / LightGBM / CatBoost) desde
`nba_game_feature_snapshots`.

Tres cabezas por modelo:
  * clasificador moneyline  -> home_win (0/1)
  * regresor spread         -> margin (home - away)
  * regresor totals         -> total_points (home + away)

Uso (desde `backend/`):

  uv run python -m app.ml.train_nba_from_db --algorithm xgb
  uv run python -m app.ml.train_nba_from_db --algorithm lgbm --val-from 2024-02-01
  uv run python -m app.ml.train_nba_from_db --algorithm catboost --calibrate

Partición temporal: filas con `game_date` < `--val-from` -> train; resto -> validación.
Sin `--val-from`, usa 80 % temporal.
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

from app.db.session import async_session_factory
from app.ml.nba_features import NBA_FEATURE_NAMES, build_nba_feature_values_for_training
from app.models.nba import NbaGame, NbaGameFeatureSnapshot

log = logging.getLogger(__name__)

_ALGORITHMS = ("xgb", "lgbm", "catboost")
_DEFAULT_OUTPUTS = {
    "xgb": "src/app/ml/artifacts/model_nba_xgb.joblib",
    "lgbm": "src/app/ml/artifacts/model_nba_lgbm.joblib",
    "catboost": "src/app/ml/artifacts/model_nba_catboost.joblib",
}
_DEFAULT_VERSIONS = {
    "xgb": "nba-xgb-db-v1",
    "lgbm": "nba-lgbm-db-v1",
    "catboost": "nba-catboost-db-v1",
}


async def _load_xy(
    session: AsyncSession,
    *,
    season: str | None,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.int_],
    NDArray[np.float64],
    NDArray[np.float64],
    list[dt.date],
]:
    stmt = (
        select(NbaGameFeatureSnapshot, NbaGame)
        .join(NbaGame, NbaGame.game_id == NbaGameFeatureSnapshot.game_id)
        .where(NbaGameFeatureSnapshot.home_win.is_not(None))
        .where(NbaGameFeatureSnapshot.total_points.is_not(None))
        .where(NbaGameFeatureSnapshot.margin.is_not(None))
        .order_by(NbaGame.game_date, NbaGame.game_id)
    )
    if season is not None:
        stmt = stmt.where(NbaGame.season == season)

    rows = (await session.execute(stmt)).all()
    if len(rows) < 20:
        raise RuntimeError(
            f"Need at least 20 labeled NBA games for training; got {len(rows)}. "
            "Run sync_season + rebuild_nba_game_feature_snapshots first."
        )

    xs: list[list[float]] = []
    y_home: list[int] = []
    y_margin: list[float] = []
    y_total: list[float] = []
    dates: list[dt.date] = []
    for snap, game in rows:
        xs.append(build_nba_feature_values_for_training(snap))
        assert snap.home_win is not None
        assert snap.margin is not None
        assert snap.total_points is not None
        y_home.append(int(snap.home_win))
        y_margin.append(float(snap.margin))
        y_total.append(float(snap.total_points))
        dates.append(game.game_date)

    x_arr = np.asarray(xs, dtype=np.float64)
    _log_feature_health(x_arr)
    return (
        x_arr,
        np.asarray(y_home, dtype=np.int_),
        np.asarray(y_margin, dtype=np.float64),
        np.asarray(y_total, dtype=np.float64),
        dates,
    )


def _log_feature_health(x: NDArray[np.float64]) -> None:
    feat_cols = x[:, :-1] if x.shape[1] > 1 else x
    std = np.std(feat_cols, axis=0)
    nz = int(np.count_nonzero(std > 1e-6))
    log.info(
        "features: rows=%d cols=%d | cols con std>1e-6: %d/%d | mean std=%.4f",
        x.shape[0],
        x.shape[1],
        nz,
        feat_cols.shape[1],
        float(np.mean(std)),
    )
    if nz < 4:
        log.warning("Las features están muy planas: revisa sync_season + " "rebuild_nba_game_feature_snapshots.")


def _split_temporal(
    x: NDArray[np.float64],
    dates: list[dt.date],
    val_from: dt.date | None,
) -> tuple[NDArray[np.bool_], str]:
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
            f"Partición inválida: train={nt}, val={nv} (se requiere train>=10 y val>=5). " f"val_from={val_from!s}."
        )
    return mask_train, split_label


def _build_models(algorithm: str, args: argparse.Namespace) -> tuple[Any, Any, Any]:
    """Devuelve (clf_moneyline, reg_margin, reg_total) para el algoritmo elegido."""
    if algorithm == "xgb":
        from xgboost import XGBClassifier, XGBRegressor

        common = dict(
            n_estimators=args.trees,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            subsample=args.subsample,
            colsample_bytree=args.colsample_bytree,
            random_state=42,
        )
        clf = XGBClassifier(**common, eval_metric="logloss")
        return clf, XGBRegressor(**common), XGBRegressor(**common)

    if algorithm == "lgbm":
        from lightgbm import LGBMClassifier, LGBMRegressor

        common = dict(
            n_estimators=args.trees,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            subsample=args.subsample,
            colsample_bytree=args.colsample_bytree,
            random_state=42,
            verbose=-1,
        )
        clf = LGBMClassifier(**common)
        return clf, LGBMRegressor(**common), LGBMRegressor(**common)

    if algorithm == "catboost":
        from catboost import CatBoostClassifier, CatBoostRegressor

        common = dict(
            iterations=args.trees,
            depth=min(args.max_depth, 16),
            learning_rate=args.learning_rate,
            random_state=42,
            verbose=False,
        )
        clf = CatBoostClassifier(**common)
        return clf, CatBoostRegressor(**common), CatBoostRegressor(**common)

    raise ValueError(f"Algoritmo no soportado: {algorithm}")


async def _async_main(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        x, y_home, y_margin, y_total, dates = await _load_xy(session, season=args.season)

    val_from = dt.date.fromisoformat(args.val_from) if args.val_from else None
    try:
        mask_train, split_note = _split_temporal(x, dates, val_from)
    except RuntimeError as e:
        if val_from is not None:
            log.warning("No se pudo usar val_from=%s (%s). Partición 80/20.", val_from, e)
            mask_train, split_note = _split_temporal(x, dates, None)
            split_note = "80pct_fallback_after_bad_val_from"
        else:
            raise

    x_tr, x_va = x[mask_train], x[~mask_train]
    yh_tr, yh_va = y_home[mask_train], y_home[~mask_train]
    ym_tr, ym_va = y_margin[mask_train], y_margin[~mask_train]
    yt_tr, yt_va = y_total[mask_train], y_total[~mask_train]
    log.info("split: %s | train=%d val=%d", split_note, len(yh_tr), len(yh_va))

    clf, reg_margin, reg_total = _build_models(args.algorithm, args)
    log.info("algoritmo=%s trees=%d max_depth=%d", args.algorithm, args.trees, args.max_depth)

    clf.fit(x_tr, yh_tr)
    reg_margin.fit(x_tr, ym_tr)
    reg_total.fit(x_tr, yt_tr)

    acc = accuracy_score(yh_va, clf.predict(x_va))
    mae_margin = mean_absolute_error(ym_va, reg_margin.predict(x_va))
    mae_total = mean_absolute_error(yt_va, reg_total.predict(x_va))
    proba_va = clf.predict_proba(x_va)
    val_proba_std = float(np.std(proba_va[:, 1])) if proba_va.shape[1] > 1 else None
    log.info("validation accuracy (home win): %.4f", acc)
    log.info("validation MAE margin: %.4f | MAE total: %.4f", mae_margin, mae_total)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "algorithm": args.algorithm,
        "feature_names": NBA_FEATURE_NAMES,
        "trained_on_games": int(len(dates)),
        "val_from_requested": val_from.isoformat() if val_from else None,
        "split_mode": split_note,
        "metrics": {
            "val_accuracy_home": acc,
            "val_mae_margin": mae_margin,
            "val_mae_total_points": mae_total,
            "val_proba_home_std": val_proba_std,
        },
    }
    bundle = {
        "clf": clf,
        "reg_margin": reg_margin,
        "reg_total": reg_total,
        "feature_names": NBA_FEATURE_NAMES,
        "model_version": args.model_version,
        "training_meta": json.dumps(meta),
    }
    joblib.dump(bundle, out)
    log.info(
        "wrote %s [algorithm=%s version=%s]",
        out.resolve(),  # noqa: ASYNC240  # cheap one-shot local FS resolve
        args.algorithm,
        args.model_version,
    )

    if getattr(args, "calibrate", False):
        from app.ml.calibration import fit_calibration_from_arrays, save_calibration

        log.info("Ajustando capa de calibración sobre el set de validación...")
        raw = proba_va[:, 1] if proba_va.shape[1] > 1 else proba_va[:, 0]
        calibrator = fit_calibration_from_arrays(raw, yh_va)
        cal_path = save_calibration(args.model_version, calibrator)
        log.info("calibración guardada en %s", cal_path)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    p = argparse.ArgumentParser(description="Entrena modelos NBA (3 cabezas) desde snapshots.")
    p.add_argument("--algorithm", choices=list(_ALGORITHMS), default="xgb")
    p.add_argument("--output", default=None, help="Ruta joblib de salida")
    p.add_argument("--season", default=None, help="Restringir a temporada, p. ej. 2023-24")
    p.add_argument("--val-from", default=None, help="YYYY-MM-DD: validación desde esta fecha")
    p.add_argument("--trees", type=int, default=300, help="n_estimators / iterations")
    p.add_argument("--max-depth", type=int, default=6)
    p.add_argument("--learning-rate", type=float, default=0.05)
    p.add_argument("--subsample", type=float, default=0.8)
    p.add_argument("--colsample-bytree", type=float, default=0.8)
    p.add_argument("--model-version", default=None)
    p.add_argument("--calibrate", action="store_true")

    args = p.parse_args(argv)
    if args.output is None:
        args.output = _DEFAULT_OUTPUTS[args.algorithm]
    if args.model_version is None:
        args.model_version = _DEFAULT_VERSIONS[args.algorithm]

    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
