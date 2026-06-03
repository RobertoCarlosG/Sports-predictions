"""Post-hoc probability calibration for the home-win classifier.

Fits an isotonic regression that maps the model's raw probabilities to
calibrated ones using historical prediction results (predicted prob vs
actual outcome). This corrects systematic over- or under-confidence
without retraining the base model.

Usage (standalone):
  uv run python -m app.cli.calibrate --model-version rf-db-v1

Usage (after training):
  uv run python -m app.ml.train_from_db --bayesian --calibrate
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import joblib
import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sklearn.isotonic import IsotonicRegression

log = logging.getLogger(__name__)

_ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def _calibration_path(model_version: str) -> Path:
    safe = model_version.replace("/", "_").replace("@", "_at_")
    return _ARTIFACTS_DIR / f"calibration_{safe}.joblib"


def fit_calibration_from_arrays(
    probs: NDArray[np.float64],
    outcomes: NDArray[np.int_],
) -> "IsotonicRegression":
    """Fit an isotonic regression calibrator on (raw_prob, actual_outcome) pairs.

    Returns a fitted IsotonicRegression that maps [0,1] → [0,1].
    """
    from sklearn.isotonic import IsotonicRegression

    if len(probs) < 10:
        raise ValueError(f"Need at least 10 samples to fit calibration; got {len(probs)}")

    ir = IsotonicRegression(out_of_bounds="clip")
    ir.fit(probs, outcomes)

    base_acc = float(np.mean((probs >= 0.5).astype(int) == outcomes))
    cal_preds = ir.predict(probs)
    cal_acc = float(np.mean((cal_preds >= 0.5).astype(int) == outcomes))
    log.info(
        "calibration fit: n=%d | base acc=%.4f | calibrated acc=%.4f | mean raw=%.4f | mean cal=%.4f",
        len(probs),
        base_acc,
        cal_acc,
        float(np.mean(probs)),
        float(np.mean(cal_preds)),
    )
    return ir


async def fit_calibration_from_db(
    session: "AsyncSession",
    model_version: str,
) -> tuple["IsotonicRegression", int]:
    """Load evaluated predictions from DB and fit a calibrator.

    Returns (calibrator, n_samples).
    """
    from sqlalchemy import select

    from app.models.mlb import GamePredictionCache

    stmt = select(GamePredictionCache).where(
        GamePredictionCache.model_version.startswith(model_version.split("@")[0]),
        GamePredictionCache.home_win_probability.is_not(None),
        GamePredictionCache.actual_winner.is_not(None),
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        raise ValueError(
            f"No evaluated predictions found for model version '{model_version}'. "
            "Run the game sync + evaluate-pending first."
        )

    probs = np.array([r.home_win_probability for r in rows], dtype=np.float64)
    outcomes = np.array(
        [1 if r.actual_winner == "home" else 0 for r in rows], dtype=np.int_
    )
    calibrator = fit_calibration_from_arrays(probs, outcomes)
    return calibrator, len(rows)


def save_calibration(model_version: str, calibrator: "IsotonicRegression") -> Path:
    path = _calibration_path(model_version)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(calibrator, path)
    log.info("calibration saved: %s", path)
    return path


def load_calibration(model_version: str) -> "IsotonicRegression | None":
    """Load calibrator for a model version. Returns None if not found."""
    base = model_version.split("@")[0]
    path = _calibration_path(base)
    if not path.is_file():
        path = _calibration_path(model_version)
    if not path.is_file():
        return None
    try:
        cal = joblib.load(path)
        log.debug("calibration loaded from %s", path)
        return cal
    except Exception:
        log.warning("failed to load calibration from %s", path, exc_info=True)
        return None


def apply_calibration(raw_prob: float, calibrator: "IsotonicRegression | None") -> float:
    """Apply calibration if available; otherwise return raw probability unchanged."""
    if calibrator is None:
        return raw_prob
    result = float(calibrator.predict([raw_prob])[0])
    return max(0.0, min(1.0, result))
