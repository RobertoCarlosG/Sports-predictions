"""Tests unitarios de ``app.core.admin_security`` (sin base de datos)."""

from __future__ import annotations

import datetime as dt

import pytest

from app.core.admin_security import (
    create_access_token,
    decode_access_token,
    decode_token_expires_at_utc,
    hash_password,
    verify_password,
)


def test_hash_and_verify_roundtrip() -> None:
    h = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", h)
    assert not verify_password("wrong", h)


def test_create_and_decode_access_token() -> None:
    secret = "test_secret_key_for_jwt_hs256_min_length_ok"
    token = create_access_token(secret=secret, subject="alice", expire_minutes=60)
    assert decode_access_token(token, secret) == "alice"


def test_decode_expires_at_roundtrip() -> None:
    secret = "test_secret_key_for_jwt_hs256_min_length_ok"
    token = create_access_token(secret=secret, subject="bob", expire_minutes=5)
    exp = decode_token_expires_at_utc(token, secret)
    assert exp is not None
    assert exp > dt.datetime.now(dt.UTC)


def test_decode_invalid_token_returns_none_for_expires() -> None:
    assert decode_token_expires_at_utc("not-a.jwt", "secret") is None


def test_password_too_long_raises() -> None:
    too_long = "x" * 73
    with pytest.raises(ValueError, match="72"):
        hash_password(too_long)
