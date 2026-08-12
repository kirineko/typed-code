"""Future browser clients inherit a loopback, same-origin security boundary."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from typed_code.service.app_state import AppState
from typed_code.service.runtime_identity import ServiceOwner


@pytest.mark.asyncio
async def test_cross_origin_browser_request_is_rejected_before_mutation(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    state, workspace, _token = api_env
    headers = {**auth_headers, "Origin": "https://untrusted.example"}

    response = await client.post(
        "/v1/sessions",
        headers=headers,
        json={
            "workspace_path": str(workspace),
            "provider": "cliproxy",
            "model": "gpt-5.6-sol",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "unauthorized"
    assert await state.repository.list_sessions() == []


@pytest.mark.asyncio
async def test_same_origin_browser_request_remains_compatible(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    _state, workspace, _token = api_env
    headers = {**auth_headers, "Origin": "http://test"}

    response = await client.post(
        "/v1/sessions",
        headers=headers,
        json={
            "workspace_path": str(workspace),
            "provider": "cliproxy",
            "model": "gpt-5.6-sol",
        },
    )

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_managed_service_rejects_non_loopback_host(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    state, _workspace, _token = api_env
    owner = ServiceOwner.acquire(state.settings.data_dir)
    state.service_owner = owner
    owner.publish_descriptor("http://127.0.0.1:8741")
    try:
        response = await client.get(
            "/v1/models",
            headers={**auth_headers, "Host": "attacker.example"},
        )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "unauthorized"
    finally:
        owner.close()
        state.service_owner = None
