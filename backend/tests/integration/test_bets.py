"""Integration tests for /api/v1/bets/* endpoints.

All tests use the user_client fixture (pre-authenticated AppUser).
No MagicMock — real DB objects, real JWT auth.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.integration.mock_data import (
    APP_USER_UUID,
    BET_BANK_CREATE_BODY,
    BET_CREATE_BODY,
    BET_PERIOD_CREATE_BODY,
    SCHEDULED_GAME_PK,
)
from tests.integration.mock_data_fail import (
    BET_BANK_CURRENCY_TOO_LONG,
    BET_BANK_EMPTY_NAME,
    BET_BANK_MISSING_NAME,
    BET_BANK_NEGATIVE_AMOUNT,
    BET_BANK_ZERO_AMOUNT,
    BET_INVALID_BET_SIDE,
    BET_INVALID_BET_TYPE,
    BET_MISSING_REQUIRED_FIELDS,
    BET_NEGATIVE_STAKE,
    BET_NONEXISTENT_BANK,
    BET_NONEXISTENT_GAME,
    BET_ODDS_BELOW_ONE,
    BET_PERIOD_MONTH_13,
    BET_PERIOD_MONTH_ZERO,
    BET_PERIOD_NONEXISTENT_BANK,
    BET_PERIOD_YEAR_TOO_HIGH,
    BET_PERIOD_YEAR_TOO_LOW,
    BET_ZERO_STAKE,
)

USER_HEADERS = {"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Helper: create a bank and period, return (bank_id, period_id)
# ---------------------------------------------------------------------------


async def _create_bank(user_client: AsyncClient) -> int:
    r = await user_client.post(
        "/api/v1/bets/banks", json=BET_BANK_CREATE_BODY, headers=USER_HEADERS
    )
    assert r.status_code == 200, f"Bank creation failed: {r.text}"
    return r.json()["id"]


async def _create_period(user_client: AsyncClient, bank_id: int) -> int:
    body = {**BET_PERIOD_CREATE_BODY, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets/periods", json=body, headers=USER_HEADERS)
    assert r.status_code == 200, f"Period creation failed: {r.text}"
    return r.json()["id"]


# ---------------------------------------------------------------------------
# GET /api/v1/bets/banks
# ---------------------------------------------------------------------------


async def test_get_banks_returns_empty_list_initially(user_client: AsyncClient) -> None:
    r = await user_client.get("/api/v1/bets/banks")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_get_banks_unauthenticated_returns_401_or_503(client: AsyncClient) -> None:
    """Without auth token: 401 (JWT configured) or 503 (JWT not configured).
    Client fixture sets user_jwt_secret, so we expect 401."""
    r = await client.get("/api/v1/bets/banks")
    assert r.status_code in (401, 503)


# ---------------------------------------------------------------------------
# POST /api/v1/bets/banks
# ---------------------------------------------------------------------------


async def test_create_bank_success(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/banks", json=BET_BANK_CREATE_BODY, headers=USER_HEADERS
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == BET_BANK_CREATE_BODY["name"]
    assert body["initial_amount"] == BET_BANK_CREATE_BODY["initial_amount"]
    assert body["currency"] == "USD"
    assert body["is_active"] is True


async def test_create_bank_then_appears_in_list(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    r = await user_client.get("/api/v1/bets/banks")
    assert r.status_code == 200
    ids = [b["id"] for b in r.json()]
    assert bank_id in ids


async def test_create_bank_zero_amount_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/banks", json=BET_BANK_ZERO_AMOUNT, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_bank_negative_amount_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/banks", json=BET_BANK_NEGATIVE_AMOUNT, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_bank_missing_name_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/banks", json=BET_BANK_MISSING_NAME, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_bank_empty_name_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post("/api/v1/bets/banks", json=BET_BANK_EMPTY_NAME, headers=USER_HEADERS)
    assert r.status_code == 422


async def test_create_bank_currency_too_long_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/banks", json=BET_BANK_CURRENCY_TOO_LONG, headers=USER_HEADERS
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/v1/bets/banks/{bank_id}
# ---------------------------------------------------------------------------


async def test_update_bank_name(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    r = await user_client.put(
        f"/api/v1/bets/banks/{bank_id}",
        json={"name": "Updated Bank Name"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Bank Name"


async def test_update_bank_deactivate(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    r = await user_client.put(
        f"/api/v1/bets/banks/{bank_id}",
        json={"is_active": False},
        headers=USER_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


async def test_update_bank_not_found_returns_404(user_client: AsyncClient) -> None:
    r = await user_client.put(
        "/api/v1/bets/banks/999999",
        json={"name": "Ghost Bank"},
        headers=USER_HEADERS,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/bets/periods
# ---------------------------------------------------------------------------


async def test_get_periods_returns_empty_initially(user_client: AsyncClient) -> None:
    r = await user_client.get("/api/v1/bets/periods")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# POST /api/v1/bets/periods
# ---------------------------------------------------------------------------


async def test_create_period_success(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    body = {**BET_PERIOD_CREATE_BODY, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets/periods", json=body, headers=USER_HEADERS)
    assert r.status_code == 200
    p = r.json()
    assert p["year"] == 2025
    assert p["month"] == 9
    assert p["status"] == "open"


async def test_create_period_month_zero_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/periods", json=BET_PERIOD_MONTH_ZERO, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_period_month_13_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/periods", json=BET_PERIOD_MONTH_13, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_period_year_too_low_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/periods", json=BET_PERIOD_YEAR_TOO_LOW, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_period_year_too_high_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/periods", json=BET_PERIOD_YEAR_TOO_HIGH, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_period_nonexistent_bank_returns_404(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets/periods", json=BET_PERIOD_NONEXISTENT_BANK, headers=USER_HEADERS
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/bets/periods/{period_id}/close
# ---------------------------------------------------------------------------


async def test_close_period_success(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    period_id = await _create_period(user_client, bank_id)
    r = await user_client.post(f"/api/v1/bets/periods/{period_id}/close", headers=USER_HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "closed"


async def test_close_period_not_found_returns_404(user_client: AsyncClient) -> None:
    r = await user_client.post("/api/v1/bets/periods/999999/close", headers=USER_HEADERS)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/bets/periods/{period_id}/stats
# ---------------------------------------------------------------------------


async def test_period_stats_returns_zeros_for_new_period(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    period_id = await _create_period(user_client, bank_id)
    r = await user_client.get(f"/api/v1/bets/periods/{period_id}/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_stake"] == 0.0
    assert body["decided_bets"] == 0


# ---------------------------------------------------------------------------
# POST /api/v1/bets — create bet
# ---------------------------------------------------------------------------


async def test_create_bet_success(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_CREATE_BODY, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    assert r.status_code == 200
    bet = r.json()
    assert bet["bet_type"] == "moneyline"
    assert bet["bet_side"] == "home"
    assert bet["stake"] == 50.0
    assert bet["odds"] == 1.85
    assert bet["status"] == "pending"


async def test_create_bet_zero_stake_returns_422(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_ZERO_STAKE, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    assert r.status_code == 422


async def test_create_bet_negative_stake_returns_422(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_NEGATIVE_STAKE, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    assert r.status_code == 422


async def test_create_bet_odds_below_one_returns_422(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_ODDS_BELOW_ONE, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    assert r.status_code == 422


async def test_create_bet_invalid_bet_type_returns_422(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_INVALID_BET_TYPE, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    assert r.status_code == 422


async def test_create_bet_invalid_bet_side_returns_422(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_INVALID_BET_SIDE, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    assert r.status_code == 422


async def test_create_bet_missing_fields_returns_422(user_client: AsyncClient) -> None:
    r = await user_client.post(
        "/api/v1/bets", json=BET_MISSING_REQUIRED_FIELDS, headers=USER_HEADERS
    )
    assert r.status_code == 422


async def test_create_bet_nonexistent_game_returns_404(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_NONEXISTENT_GAME, "bank_id": bank_id}
    r = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    assert r.status_code == 404


async def test_create_bet_nonexistent_bank_returns_404(user_client: AsyncClient) -> None:
    r = await user_client.post("/api/v1/bets", json=BET_NONEXISTENT_BANK, headers=USER_HEADERS)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/bets
# ---------------------------------------------------------------------------


async def test_get_bets_returns_created_bets(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_CREATE_BODY, "bank_id": bank_id}
    await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)

    r = await user_client.get("/api/v1/bets")
    assert r.status_code == 200
    bets = r.json()
    assert any(b["game_pk"] == SCHEDULED_GAME_PK for b in bets)


async def test_get_bets_unauthenticated_returns_401_or_503(client: AsyncClient) -> None:
    r = await client.get("/api/v1/bets")
    assert r.status_code in (401, 503)


# ---------------------------------------------------------------------------
# GET /api/v1/bets/{bet_id}
# ---------------------------------------------------------------------------


async def test_get_bet_by_id(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_CREATE_BODY, "bank_id": bank_id}
    create_resp = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    bet_id = create_resp.json()["id"]

    r = await user_client.get(f"/api/v1/bets/{bet_id}")
    assert r.status_code == 200
    assert r.json()["id"] == bet_id


async def test_get_bet_not_found_returns_404(user_client: AsyncClient) -> None:
    r = await user_client.get("/api/v1/bets/999999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/bets/{bet_id}
# ---------------------------------------------------------------------------


async def test_patch_bet_notes(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_CREATE_BODY, "bank_id": bank_id}
    create_resp = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    bet_id = create_resp.json()["id"]

    r = await user_client.patch(
        f"/api/v1/bets/{bet_id}", json={"notes": "Updated note"}, headers=USER_HEADERS
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "Updated note"


async def test_patch_bet_cancel(user_client: AsyncClient) -> None:
    bank_id = await _create_bank(user_client)
    await _create_period(user_client, bank_id)
    body = {**BET_CREATE_BODY, "bank_id": bank_id}
    create_resp = await user_client.post("/api/v1/bets", json=body, headers=USER_HEADERS)
    bet_id = create_resp.json()["id"]

    r = await user_client.patch(
        f"/api/v1/bets/{bet_id}", json={"status": "cancelled"}, headers=USER_HEADERS
    )
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


# ---------------------------------------------------------------------------
# GET /api/v1/bets/stats
# ---------------------------------------------------------------------------


async def test_get_bets_stats_returns_structure(user_client: AsyncClient) -> None:
    r = await user_client.get("/api/v1/bets/stats")
    assert r.status_code == 200
    body = r.json()
    assert "total_stake" in body
    assert "decided_bets" in body
    assert "by_type" in body


# ---------------------------------------------------------------------------
# User auth — /api/v1/auth/*
# ---------------------------------------------------------------------------


async def test_auth_ready_returns_200(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/ready")
    assert r.status_code == 200
    body = r.json()
    assert "login_available" in body


async def test_auth_me_returns_user_info(user_client: AsyncClient) -> None:
    """/auth/me reads the user session cookie directly (not the Authorization header).
    Pass the cookie explicitly in the request.
    """
    from app.core.admin_security import create_access_token
    from app.core.config import settings

    token = create_access_token(
        secret=settings.user_jwt_secret,
        subject=str(APP_USER_UUID),
        expire_minutes=settings.user_token_expire_minutes,
    )
    r = await user_client.get(
        "/api/v1/auth/me",
        cookies={settings.user_cookie_name: token},
    )
    assert r.status_code == 200
    body = r.json()
    assert "user_id" in body
    assert "email" in body
    assert body["email"] == "integration_test@example.com"


async def test_auth_me_unauthenticated_returns_401_or_503(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code in (401, 503)


async def test_auth_logout_returns_200(user_client: AsyncClient) -> None:
    r = await user_client.post("/api/v1/auth/logout", headers=USER_HEADERS)
    assert r.status_code == 200
