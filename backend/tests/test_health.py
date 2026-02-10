"""
Integration tests for health check endpoints.

These are the simplest tests — they verify the app starts up
and can respond to basic requests. If these fail, everything else
will fail too, so they're a good canary.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """GET / returns service info."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Adult Learning Coaching Agent"
    assert data["status"] == "running"
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET /health returns database status."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "environment" in data
