"""Invalid/edge-case data for testing failure responses in integration tests.

Each entry documents what constraint it violates and what HTTP status is expected.
No MagicMock — these are plain dicts/values representing bad inputs.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Games — path param failures
# ---------------------------------------------------------------------------

NONEXISTENT_GAME_PK = 999999999   # no game with this PK in test DB
INVALID_GAME_PK_STR = "not-a-number"   # type error → 422

# ---------------------------------------------------------------------------
# Auth failures — admin
# ---------------------------------------------------------------------------

WRONG_PASSWORD_LOGIN_BODY: dict[str, Any] = {
    "username": "integration_admin",
    "password": "wrong_password_that_doesnt_match",
}

NONEXISTENT_USER_LOGIN_BODY: dict[str, Any] = {
    "username": "no_such_user",
    "password": "any_password",
}

EMPTY_USERNAME_LOGIN_BODY: dict[str, Any] = {
    "username": "",
    "password": "some_password",
}

MISSING_USERNAME_LOGIN_BODY: dict[str, Any] = {
    "password": "some_password",
}

MISSING_PASSWORD_LOGIN_BODY: dict[str, Any] = {
    "username": "integration_admin",
}

# Headers without required CSRF header (admin routes require X-Requested-With)
NO_CSRF_HEADERS: dict[str, str] = {"Content-Type": "application/json"}

# ---------------------------------------------------------------------------
# Prediction — service not available
# ---------------------------------------------------------------------------

# ?model=xgb when XGBoost not loaded → 503 (tested by not setting xgb service)
XGB_MODEL_QUERY = "?model=xgb"

# Invalid model param value → 422
INVALID_MODEL_PARAM = "?model=invalid_model"

# ---------------------------------------------------------------------------
# BetBank — validation failures
# ---------------------------------------------------------------------------

BET_BANK_ZERO_AMOUNT: dict[str, Any] = {
    "name": "Invalid Bank",
    "initial_amount": 0.0,   # must be > 0
    "currency": "USD",
}

BET_BANK_NEGATIVE_AMOUNT: dict[str, Any] = {
    "name": "Invalid Bank",
    "initial_amount": -100.0,   # must be > 0
    "currency": "USD",
}

BET_BANK_MISSING_NAME: dict[str, Any] = {
    "initial_amount": 500.0,
    "currency": "USD",
}

BET_BANK_EMPTY_NAME: dict[str, Any] = {
    "name": "",   # min_length=1
    "initial_amount": 500.0,
    "currency": "USD",
}

BET_BANK_CURRENCY_TOO_LONG: dict[str, Any] = {
    "name": "My Bank",
    "initial_amount": 500.0,
    "currency": "TOOLONGCURRENCY",   # max 8 chars
}

# ---------------------------------------------------------------------------
# BetPeriod — validation failures
# ---------------------------------------------------------------------------

BET_PERIOD_MONTH_ZERO: dict[str, Any] = {
    "bank_id": 1,
    "year": 2025,
    "month": 0,   # min=1
}

BET_PERIOD_MONTH_13: dict[str, Any] = {
    "bank_id": 1,
    "year": 2025,
    "month": 13,   # max=12
}

BET_PERIOD_YEAR_TOO_LOW: dict[str, Any] = {
    "bank_id": 1,
    "year": 1999,   # min=2000
    "month": 6,
}

BET_PERIOD_YEAR_TOO_HIGH: dict[str, Any] = {
    "bank_id": 1,
    "year": 2101,   # max=2100
    "month": 6,
}

BET_PERIOD_MISSING_BANK: dict[str, Any] = {
    "year": 2025,
    "month": 9,
    # missing bank_id
}

BET_PERIOD_NONEXISTENT_BANK: dict[str, Any] = {
    "bank_id": 999999,   # does not exist
    "year": 2025,
    "month": 9,
}

# ---------------------------------------------------------------------------
# Bet — validation failures
# ---------------------------------------------------------------------------

BET_ZERO_STAKE: dict[str, Any] = {
    "bank_id": 1,
    "game_pk": 748000,
    "bet_type": "moneyline",
    "bet_side": "home",
    "stake": 0.0,   # must be > 0
    "odds": 1.85,
}

BET_NEGATIVE_STAKE: dict[str, Any] = {
    "bank_id": 1,
    "game_pk": 748000,
    "bet_type": "moneyline",
    "bet_side": "home",
    "stake": -10.0,
    "odds": 1.85,
}

BET_ODDS_BELOW_ONE: dict[str, Any] = {
    "bank_id": 1,
    "game_pk": 748000,
    "bet_type": "moneyline",
    "bet_side": "home",
    "stake": 50.0,
    "odds": 0.5,   # must be >= 1.0
}

BET_INVALID_BET_TYPE: dict[str, Any] = {
    "bank_id": 1,
    "game_pk": 748000,
    "bet_type": "spread",   # not in ["moneyline", "over_under"]
    "bet_side": "home",
    "stake": 50.0,
    "odds": 1.85,
}

BET_INVALID_BET_SIDE: dict[str, Any] = {
    "bank_id": 1,
    "game_pk": 748000,
    "bet_type": "moneyline",
    "bet_side": "push",   # not in ["home", "away", "over", "under"]
    "stake": 50.0,
    "odds": 1.85,
}

BET_MISSING_REQUIRED_FIELDS: dict[str, Any] = {
    "game_pk": 748000,
    # missing: bank_id, bet_type, bet_side, stake, odds
}

BET_NONEXISTENT_GAME: dict[str, Any] = {
    "bank_id": 1,
    "game_pk": 999999999,   # does not exist
    "bet_type": "moneyline",
    "bet_side": "home",
    "stake": 50.0,
    "odds": 1.85,
}

BET_NONEXISTENT_BANK: dict[str, Any] = {
    "bank_id": 999999,   # does not exist
    "game_pk": 748000,
    "bet_type": "moneyline",
    "bet_side": "home",
    "stake": 50.0,
    "odds": 1.85,
}

# ---------------------------------------------------------------------------
# MLB sync — validation failures
# ---------------------------------------------------------------------------

MLB_SYNC_END_BEFORE_START: dict[str, Any] = {
    "start_date": "2025-08-15",
    "end_date": "2025-08-10",   # end before start
    "fetch_details": False,
}

MLB_SYNC_MISSING_START: dict[str, Any] = {
    "end_date": "2025-08-11",
    "fetch_details": False,
}

MLB_SYNC_MISSING_END: dict[str, Any] = {
    "start_date": "2025-08-10",
    "fetch_details": False,
}

MLB_SYNC_INVALID_DATE: dict[str, Any] = {
    "start_date": "not-a-date",
    "end_date": "2025-08-11",
}

# ---------------------------------------------------------------------------
# Admin rebuild-snapshots — validation failures
# ---------------------------------------------------------------------------

REBUILD_SNAPSHOTS_WINDOW_ZERO: dict[str, Any] = {
    "window": 0,   # min=1
}

REBUILD_SNAPSHOTS_WINDOW_TOO_LARGE: dict[str, Any] = {
    "window": 51,   # max=50
}

# ---------------------------------------------------------------------------
# Admin pagination — validation failures
# ---------------------------------------------------------------------------

PAGINATION_LIMIT_ZERO: dict[str, Any] = {"limit": 0}       # min=1
PAGINATION_LIMIT_TOO_HIGH: dict[str, Any] = {"limit": 201}  # max=200
PAGINATION_NEGATIVE_OFFSET: dict[str, Any] = {"offset": -1}  # min=0

# ---------------------------------------------------------------------------
# Backtest — validation failures
# ---------------------------------------------------------------------------

BACKTEST_CONFIDENCE_BELOW_HALF: dict[str, Any] = {
    "min_confidence": 0.49,   # min=0.5
}

BACKTEST_CONFIDENCE_ABOVE_ONE: dict[str, Any] = {
    "min_confidence": 1.01,   # max=1.0
}

# ---------------------------------------------------------------------------
# Admin train — validation failures
# ---------------------------------------------------------------------------

TRAIN_TREES_TOO_FEW: dict[str, Any] = {
    "trees": 9,   # min=10
}

TRAIN_TREES_TOO_MANY: dict[str, Any] = {
    "trees": 501,   # max=500
}

TRAIN_MAX_DEPTH_TOO_SHALLOW: dict[str, Any] = {
    "max_depth": 1,   # min=2
}

TRAIN_MAX_DEPTH_TOO_DEEP: dict[str, Any] = {
    "max_depth": 49,   # max=48
}

TRAIN_MIN_LEAF_TOO_BIG: dict[str, Any] = {
    "min_samples_leaf": 51,   # max=50
}

# ---------------------------------------------------------------------------
# Edge cases — boundary values that SHOULD succeed (but are interesting)
# ---------------------------------------------------------------------------

BOUNDARY_VALID = {
    "pagination_limit_one": {"limit": 1},           # min valid
    "pagination_limit_max": {"limit": 200},         # max valid
    "bet_odds_exactly_one": {"odds": 1.0},          # exact minimum
    "bet_bank_currency_8chars": {"currency": "LONGCURR"},  # exactly 8 chars
}
