"""Bayesian hyperparameter search using Optuna (TPE sampler).

The Optuna study persists in a SQLite file under ml/artifacts/ so each
manual training run builds on prior knowledge — the search gets smarter
each time rather than starting from scratch.

Called from train_from_db.py via --bayesian flag.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

log = logging.getLogger(__name__)

_ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
_DEFAULT_N_TRIALS = 30


def _study_db_url(algorithm: str) -> str:
    path = _ARTIFACTS_DIR / f"optuna_study_{algorithm}.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"


def _rf_objective(
    trial: Any,
    x_tr: NDArray[np.float64],
    x_va: NDArray[np.float64],
    yh_tr: NDArray[np.int_],
    yh_va: NDArray[np.int_],
    yr_tr: NDArray[np.float64],
    yr_va: NDArray[np.float64],
) -> float:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.metrics import accuracy_score, mean_absolute_error

    n_estimators = trial.suggest_int("n_estimators", 64, 400)
    max_depth = trial.suggest_int("max_depth", 4, 24)
    min_samples_leaf = trial.suggest_int("min_samples_leaf", 1, 8)
    max_features = trial.suggest_categorical("max_features", ["sqrt", "log2", None])

    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        max_features=max_features,
        random_state=42,
        n_jobs=-1,
    )
    reg = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        max_features=max_features,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(x_tr, yh_tr)
    reg.fit(x_tr, yr_tr)

    acc = accuracy_score(yh_va, clf.predict(x_va))
    mae = mean_absolute_error(yr_va, reg.predict(x_va))

    # Combined score: maximize accuracy, penalize high MAE (normalize MAE to ~same scale)
    return float(acc - mae / 20.0)


def _xgb_objective(
    trial: Any,
    x_tr: NDArray[np.float64],
    x_va: NDArray[np.float64],
    yh_tr: NDArray[np.int_],
    yh_va: NDArray[np.int_],
    yr_tr: NDArray[np.float64],
    yr_va: NDArray[np.float64],
) -> float:
    from sklearn.metrics import accuracy_score, mean_absolute_error
    from xgboost import XGBClassifier, XGBRegressor

    n_estimators = trial.suggest_int("n_estimators", 64, 400)
    max_depth = trial.suggest_int("max_depth", 3, 10)
    learning_rate = trial.suggest_float("learning_rate", 0.01, 0.3, log=True)
    subsample = trial.suggest_float("subsample", 0.5, 1.0)
    colsample_bytree = trial.suggest_float("colsample_bytree", 0.5, 1.0)
    min_child_weight = trial.suggest_int("min_child_weight", 1, 10)

    clf = XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        random_state=42,
        eval_metric="logloss",
        verbosity=0,
    )
    reg = XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        random_state=42,
        verbosity=0,
    )
    clf.fit(x_tr, yh_tr)
    reg.fit(x_tr, yr_tr)

    acc = accuracy_score(yh_va, clf.predict(x_va))
    mae = mean_absolute_error(yr_va, reg.predict(x_va))

    return float(acc - mae / 20.0)


def run_study(
    algorithm: str,
    x_tr: NDArray[np.float64],
    x_va: NDArray[np.float64],
    yh_tr: NDArray[np.int_],
    yh_va: NDArray[np.int_],
    yr_tr: NDArray[np.float64],
    yr_va: NDArray[np.float64],
    n_trials: int = _DEFAULT_N_TRIALS,
) -> dict[str, Any]:
    """Run Bayesian hyperparameter search. Returns best hyperparameters dict."""
    try:
        import optuna
    except ImportError as err:
        raise ImportError(
            "optuna is required for --bayesian mode. "
            "Install it: uv add optuna  (or pip install optuna)"
        ) from err

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    storage = _study_db_url(algorithm)
    study_name = f"mlb_{algorithm}_search"

    log.info("Optuna study '%s' | storage: %s | n_trials=%d", study_name, storage, n_trials)

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction="maximize",
        load_if_exists=True,
        sampler=optuna.samplers.TPESampler(seed=42),
    )

    objective_fn = _rf_objective if algorithm == "rf" else _xgb_objective

    def _objective(trial: Any) -> float:
        return objective_fn(trial, x_tr, x_va, yh_tr, yh_va, yr_tr, yr_va)

    prior_trials = len(study.trials)
    log.info("Resuming from %d prior trial(s). Running %d more.", prior_trials, n_trials)

    study.optimize(_objective, n_trials=n_trials, show_progress_bar=False)

    best = study.best_trial
    log.info(
        "Best trial #%d | score=%.4f | params=%s",
        best.number,
        best.value,
        best.params,
    )
    return dict(best.params)


def build_models_from_params(algorithm: str, params: dict[str, Any]) -> tuple[Any, Any]:
    """Construct classifier + regressor from Optuna best params."""
    if algorithm == "rf":
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

        clf = RandomForestClassifier(**params, random_state=42, n_jobs=-1)
        reg = RandomForestRegressor(**params, random_state=42, n_jobs=-1)
    else:
        from xgboost import XGBClassifier, XGBRegressor

        clf = XGBClassifier(**params, random_state=42, eval_metric="logloss", verbosity=0)
        reg = XGBRegressor(**params, random_state=42, verbosity=0)
    return clf, reg
