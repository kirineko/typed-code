"""Authentication tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_open(client: AsyncClient) -> None:
    resp = await client.get("/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["protocol_version"] == 1
    assert "deepseek" in body["providers"]


@pytest.mark.asyncio
async def test_models_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/v1/models")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_models_with_auth(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/v1/models", headers=auth_headers)
    assert resp.status_code == 200
    assert "models" in resp.json()
