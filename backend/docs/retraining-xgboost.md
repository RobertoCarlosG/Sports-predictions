# XGBoost Retraining Guide

Step-by-step instructions to train (or retrain) the XGBoost model, calibrate its probabilities, and put it live — from any starting point.

> **Already have updated snapshots?** Skip to [Step 3 — Train](#step-3--train-the-xgboost-model).

---

## Prerequisites

- You are inside the `backend/` directory for all commands
- The Python environment is active: `uv sync` has been run
- The database is reachable (`.env` has `DATABASE_URL` set)
- The backend server is running if you want to call admin API endpoints

---

## Step 1 — Verify (or Build) Historical Data

The model trains on **completed games** that have scores. First confirm you have enough.

### 1a. Check how many labeled games exist

Run this query in your DB client (Supabase, psql, etc.):

```sql
SELECT
    COUNT(*)                                            AS total_snapshots,
    COUNT(*) FILTER (WHERE home_win IS NOT NULL
                     AND   total_runs IS NOT NULL)      AS labeled_games,
    MIN(g.game_date)                                    AS earliest,
    MAX(g.game_date)                                    AS latest
FROM game_feature_snapshots s
JOIN games g ON g.game_pk = s.game_pk;
```

You need **at least 20 labeled games** to train. 100+ recommended for meaningful accuracy.

### 1b. (If needed) Backfill historical game data

If `labeled_games` is 0 or too low, fetch historical games from the MLB API first.

**Via admin API:**
```http
POST /api/v1/admin/pipeline/backfill
Authorization: <admin cookie>
Content-Type: application/json

{
  "start": "2026-04-01",
  "end": "2026-05-31",
  "fetch_details": true,
  "sleep_s": 0.3
}
```

> `sleep_s: 0.3` is a safe rate limit delay for the MLB API. Increase to `1.0` if you get 429 errors.

**Or via CLI:**
```bash
uv run python -m app.cli.backfill_history --start 2026-04-01 --end 2026-05-31
```

### 1c. (If needed) Rebuild feature snapshots

After backfill, compute the rolling stats and ERA features for each game:

**Via admin API:**
```http
POST /api/v1/admin/pipeline/rebuild-snapshots
Authorization: <admin cookie>
Content-Type: application/json

{ "season": "2026", "window": 10 }
```

**Or via CLI:**
```bash
uv run python -m app.cli.rebuild_feature_snapshots --season 2026 --window 10
```

> `window: 10` means rolling stats use the last 10 games. This is the default used by the live predictor — keep it consistent.

---

## Step 2 — Confirm Snapshots Are Ready

Re-run the query from Step 1a. You should now see `labeled_games > 50` (more is better).

Also check feature health — this tells you if the data has enough variety for the model to learn:

```bash
# This runs during training but you can preview it:
uv run python -c "
import asyncio, numpy as np
from app.db.session import async_session_factory
from app.ml.train_from_db import _load_xy

async def main():
    async with async_session_factory() as s:
        x, yh, yr, dates = await _load_xy(s, season=None)
    print(f'Rows: {len(dates)} | Home win rate: {yh.mean():.3f} | Avg runs: {yr.mean():.2f}')
    print(f'Feature std (first 12): {np.std(x[:,:12], axis=0).round(3)}')

asyncio.run(main())
"
```

If any feature has `std < 0.01` across all games, that column is flat (no signal). Check the backfill quality for that feature.

---

## Step 3 — Train the XGBoost Model

Run the training script from inside `backend/`. The script saves `artifacts/model_xgb.joblib` automatically.

### Option A — Standard training (fixed hyperparameters)

```bash
uv run python -m app.ml.train_from_db \
  --algorithm xgb \
  --season 2026
```

Default XGBoost hyperparameters:
| Parameter | Default |
|-----------|---------|
| `n_estimators` | 128 |
| `max_depth` | 6 |
| `learning_rate` | 0.05 |
| `subsample` | 0.80 |
| `colsample_bytree` | 0.80 |
| `min_child_weight` | 3 |

### Option B — Bayesian hyperparameter search (recommended after first run)

```bash
uv run python -m app.ml.train_from_db \
  --algorithm xgb \
  --season 2026 \
  --bayesian \
  --bayesian-trials 30
```

Optuna tries 30 combinations of hyperparameters and picks the best. The search is saved to `artifacts/optuna_study_xgb.db` — the next time you run with `--bayesian` it starts from what it already learned.

> First run with `--bayesian-trials 30` is fine. Subsequent runs can use `50` or more since prior knowledge is already in the study file.

### Option C — Training + calibration in one step

```bash
uv run python -m app.ml.train_from_db \
  --algorithm xgb \
  --season 2026 \
  --bayesian \
  --bayesian-trials 30 \
  --calibrate
```

`--calibrate` fits an isotonic regression on the validation set probabilities right after training and saves it as `artifacts/calibration_xgb-db-v1.joblib`. The predictor will use it automatically.

### Controlling the train/validation split

By default the script uses the **first 80%** of games (chronologically) for training and the **last 20%** for validation. You can set an explicit cutoff date:

```bash
uv run python -m app.ml.train_from_db \
  --algorithm xgb \
  --season 2026 \
  --val-from 2026-05-01
```

Games before May 1 → training. Games May 1 onward → validation.

---

## Step 4 — Read the Training Output

After training, the script prints metrics like:

```
INFO split: 80pct | train=312 val=78
INFO validation accuracy (home win): 0.5641
INFO validation MAE (total runs): 1.8732
INFO validation P(home) std=0.0812
INFO wrote src/app/ml/artifacts/model_xgb.joblib  [algorithm=xgb version=xgb-db-v1]
```

| Metric | What it means | Good sign |
|--------|--------------|-----------|
| `val accuracy (home win)` | % of wins predicted correctly on held-out games | > 0.54 (MLB is hard to predict; 55%+ is solid) |
| `val MAE (total runs)` | Average error in total runs prediction | < 2.0 |
| `val P(home) std` | Spread of predicted probabilities | > 0.05 (near 0 means the model says ~50% for every game — bad) |

**If `P(home) std` is near 0:** The model has no signal. Common causes:
- Not enough data (< 50 games) → backfill more history
- Features are flat (low variance) → check backfill quality, especially ERA and weather

---

## Step 5 — Load the Model Without Restarting

After training, the server still has the old XGBoost model in memory (or none at all). Tell it to reload:

```http
POST /api/v1/admin/model/reload-xgb
Authorization: <admin cookie>
```

**Response:**
```json
{
  "message": "XGBoost model reloaded.",
  "detail": "Version: xgb-db-v1@1a2b3c4d"
}
```

> If you prefer, you can also restart the backend — it auto-loads `artifacts/model_xgb.joblib` on startup.

---

## Step 6 — Calibrate the Probabilities (Recommended)

Calibration corrects systematic over/under-confidence. There are two ways to do it:

### Option A — From the validation set (during training, `--calibrate` flag)

Already covered in Step 3 Option C. Fast, runs immediately.

### Option B — From real game results in the DB (more accurate, requires played games)

Once the model has made predictions and games have finished (evaluated), run:

```bash
uv run python -m app.cli.calibrate --model-version xgb-db-v1
```

Or trigger via admin API:

```http
POST /api/v1/admin/model/calibrate
Authorization: <admin cookie>
```

> Run Option B periodically (e.g., once a week or after 30+ evaluated games). The more data it has, the better the calibration curve.

---

## Step 7 — Test the Predictions

Find a game_pk from today's schedule, then call the predict endpoint with `?model=xgb`:

```http
GET /api/v1/predict/746123?model=xgb
```

**Expected response:**
```json
{
  "game_pk": 746123,
  "home_win_probability": 0.587,
  "total_runs_estimate": 9.1,
  "over_under_line": 9.5,
  "model_version": "xgb-db-v1@1a2b3c4d",
  "predicted_winner": "home"
}
```

Compare with the RF model (`?model=rf` or omit the param) to see how they differ.

---

## Step 8 — Monitor and Iterate

After games finish, evaluate predictions:

```http
POST /api/v1/admin/predictions/evaluate-pending
Authorization: <admin cookie>
```

Then check accuracy:

```http
GET /api/v1/admin/predictions/metrics?model_version=xgb-db-v1
Authorization: <admin cookie>
```

When you have 30+ evaluated games, recalibrate (Step 6 Option B) and optionally retrain with more data (back to Step 3 with `--bayesian-trials 50` to deepen the Optuna search).

---

## Quick Reference

```bash
# Full pipeline from scratch (inside backend/)
uv run python -m app.cli.backfill_history --start 2026-04-01 --end 2026-05-31
uv run python -m app.cli.rebuild_feature_snapshots --season 2026 --window 10
uv run python -m app.ml.train_from_db --algorithm xgb --season 2026 --bayesian --calibrate

# Already have snapshots — just retrain
uv run python -m app.ml.train_from_db --algorithm xgb --bayesian --bayesian-trials 50 --calibrate

# Load without restart
# POST /api/v1/admin/model/reload-xgb

# Post-hoc calibration from real results (weekly)
uv run python -m app.cli.calibrate --model-version xgb-db-v1
```

---

## Artifact Files Reference

All files live under `backend/src/app/ml/artifacts/`:

| File | Created by | Purpose |
|------|-----------|---------|
| `model_xgb.joblib` | `train_from_db.py --algorithm xgb` | Trained XGBoost model bundle |
| `calibration_xgb-db-v1.joblib` | `--calibrate` flag or `calibrate.py` | Isotonic regression calibration layer |
| `optuna_study_xgb.db` | `--bayesian` flag | Persisted Optuna study (hyperparameter history) |
