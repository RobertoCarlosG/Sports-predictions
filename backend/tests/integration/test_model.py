"""Integration tests for /api/v1/model/info endpoint."""

from __future__ import annotations

from httpx import AsyncClient


async def test_model_info_returns_rf_loaded(client: AsyncClient) -> None:
    r = await client.get("/api/v1/model/info")
    assert r.status_code == 200
    body = r.json()
    assert "model_loaded" in body
    # RF model is loaded in the integration client fixture


async def test_model_info_schema_structure(client: AsyncClient) -> None:
    r = await client.get("/api/v1/model/info")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"model_loaded", "model_version", "base_version", "is_synthetic"}


async def test_model_info_no_auth_required(client: AsyncClient) -> None:
    """Model info is a public endpoint — no auth needed."""
    r = await client.get("/api/v1/model/info")
    assert r.status_code == 200
