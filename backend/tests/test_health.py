import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_large_responses_are_gzipped() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        big = await client.get("/openapi.json", headers={"Accept-Encoding": "gzip"})
        small = await client.get("/health", headers={"Accept-Encoding": "gzip"})
    assert big.status_code == 200
    assert big.headers.get("content-encoding") == "gzip"
    assert "paths" in big.json()  # httpx descomprime de forma transparente
    assert small.headers.get("content-encoding") is None  # < minimum_size
