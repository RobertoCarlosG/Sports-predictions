"""Entrena Random Forest desde `game_feature_snapshots` + `games` (Fase 3, sin sintéticos).

Uso (desde `backend/`):

  uv run python -m app.ml.train_from_db --output src/app/ml/artifacts/model.joblib
  uv run python -m app.ml.train_from_db --val-from 2025-07-01 --season 2025

Partición: filas con `game_date` < `--val-from` → train; `>= val-from` → validación.
Si no pasas `--val-from`, usa 80% temporal (primer 80% fechas train, resto val).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
from pathlib import Path

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_absolute_error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_factory
from app.ml.features import FEATURE_NAMES
from app.models.mlb import Game, GameFeatureSnapshot
from app.services.pitching_stats import DEFAULT_ERA, DEFAULT_STAFF_ERA

log = logging.getLogger(__name__)


async def _load_xy(
    session: AsyncSession,
    *,
    season: str | None,
) -> tuple[NDArray[np.float64], NDArray[np.int_], NDArray[np.float64], list[dt.date]]:
    stmt = (
        select(GameFeatureSnapshot, Game.game_date)
        .join(Game, Game.game_pk == GameFeatureSnapshot.game_pk)
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
    for snap, game_date in rows:
        xs.append(
            [
                float(snap.home_wins_roll or 0.5),
                float(snap.away_wins_roll or 0.5),
                float(snap.home_runs_avg_roll or 4.5),
                float(snap.away_runs_avg_roll or 4.5),
                float(snap.temperature_c if snap.temperature_c is not None else 20.0),
                float(snap.humidity_pct if snap.humidity_pct is not None else 50.0),
                float(snap.wind_speed_mps if snap.wind_speed_mps is not None else 2.0),
                float(snap.elevation_m if snap.elevation_m is not None else 100.0),
                float(snap.home_starter_era if snap.home_starter_era is not None else DEFAULT_ERA),
                float(snap.away_starter_era if snap.away_starter_era is not None else DEFAULT_ERA),
                float(
                    snap.home_bullpen_era if snap.home_bullpen_era is not None else DEFAULT_STAFF_ERA
                ),
                float(
                    snap.away_bullpen_era if snap.away_bullpen_era is not None else DEFAULT_STAFF_ERA
                ),
            ]
        )
        assert snap.home_win is not None and snap.total_runs is not None
        y_home.append(int(snap.home_win))
        y_runs.append(float(snap.total_runs))
        dates.append(game_date)

    x_arr = np.asarray(xs, dtype=np.float64)
    y_h = np.asarray(y_home, dtype=np.int_)
    y_r = np.asarray(y_runs, dtype=np.float64)
    return x_arr, y_h, y_r, dates


def _split_temporal(
    x: NDArray[np.float64],
    y_h: NDArray[np.int_],
    y_r: NDArray[np.float64],
    dates: list[dt.date],
    val_from: dt.date | None,
) -> tuple[NDArray, NDArray, NDArray, NDArray, NDArray, NDArray]:
    if val_from is not None:
        mask_train = np.array([d < val_from for d in dates], dtype=bool)
    else:
        n = len(dates)
        cut = int(n * 0.8)
        mask_train = np.zeros(n, dtype=bool)
        mask_train[:cut] = True
    if mask_train.sum() < 10 or (~mask_train).sum() < 5:
        raise RuntimeError("Train/val split too small; adjust --val-from or collect more data.")
    return (
        x[mask_train],
        x[~mask_train],
        y_h[mask_train],
        y_h[~mask_train],
        y_r[mask_train],
        y_r[~mask_train],
    )


async def _async_main(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        x, y_h, y_r, dates = await _load_xy(session, season=args.season)

    val_from = dt.date.fromisoformat(args.val_from) if args.val_from else None
    x_tr, x_va, yh_tr, yh_va, yr_tr, yr_va = _split_temporal(x, y_h, y_r, dates, val_from)

    clf = RandomForestClassifier(
        n_estimators=args.trees,
        random_state=42,
        max_depth=12,
        min_samples_leaf=3,
    )
    reg = RandomForestRegressor(
        n_estimators=args.trees,
        random_state=42,
        max_depth=12,
        min_samples_leaf=3,
    )
    clf.fit(x_tr, yh_tr)
    reg.fit(x_tr, yr_tr)

    pred_h = clf.predict(x_va)
    pred_r = reg.predict(x_va)
    acc = accuracy_score(yh_va, pred_h)
    mae = mean_absolute_error(yr_va, pred_r)
    log.info("validation accuracy (home win): %.4f", acc)
    log.info("validation MAE (total runs): %.4f", mae)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "feature_names": FEATURE_NAMES,
        "trained_on_games": int(len(dates)),
        "val_from": val_from.isoformat() if val_from else "80pct_split",
        "metrics": {"val_accuracy_home": acc, "val_mae_total_runs": mae},
    }
    bundle = {
        "clf": clf,
        "reg": reg,
        "feature_names": FEATURE_NAMES,
        "model_version": args.model_version,
        "training_meta": json.dumps(meta),
    }
    joblib.dump(bundle, out)
    log.info("wrote %s", out.resolve())


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Train RF from game_feature_snapshots (real labels).")
    p.add_argument(
        "--output",
        default="src/app/ml/artifacts/model_from_db.joblib",
        help="Output joblib path",
    )
    p.add_argument("--season", default=None, help="Restrict to season e.g. 2025")
    p.add_argument(
        "--val-from",
        default=None,
        help="YYYY-MM-DD: validation is games on or after this date",
    )
    p.add_argument("--trees", type=int, default=128, help="n_estimators per forest")
    p.add_argument(
        "--model-version",
        default="rf-db-v1",
        help="String returned by API predict()",
    )
    args = p.parse_args(argv)
    asyncio.run(_async_main(args))


if __name__ == "__main__":
    main()
