"""Integration tests for health endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_root_returns_service_info(client: AsyncClient) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "sports-predictions-api"
    assert "model_loaded" in body
    assert "active_model_version" in body
    # RF model is loaded in conftest
    assert body["model_loaded"] is True
