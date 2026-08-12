"""Authenticated singleton service management endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from typed_code.service.app_state import AppState


@pytest.mark.asyncio
async def test_stop_requires_authentication_and_requests_shutdown(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    state, _workspace, _token = api_env

    denied = await client.post("/v1/service/stop", json={})
    assert denied.status_code == 401
    assert not state.shutdown_requested.is_set()

    accepted = await client.post(
        "/v1/service/stop",
        headers=auth_headers,
        json={"force": False},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {
        "status": "stopping",
        "forced": False,
        "interrupted_runs": 0,
    }
    assert state.shutdown_requested.is_set()


@pytest.mark.asyncio
async def test_stop_blocks_active_work_until_force_is_explicit(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    state, workspace, _token = api_env
    created = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={
            "workspace_path": str(workspace),
            "provider": "cliproxy",
            "model": "gpt-5.6-sol",
        },
    )
    session_id = created.json()["snapshot"]["session_id"]
    await state.repository.start_turn(session_id, "active work")

    blocked = await client.post(
        "/v1/service/stop",
        headers=auth_headers,
        json={"force": False},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "conflict"
    assert "--force" in blocked.json()["error"]["message"]
    assert not state.shutdown_requested.is_set()

    forced = await client.post(
        "/v1/service/stop",
        headers=auth_headers,
        json={"force": True},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["forced"] is True
    assert forced.json()["interrupted_runs"] == 1
    snapshot = (await client.get(f"/v1/sessions/{session_id}", headers=auth_headers)).json()
    assert snapshot["phase"] == "idle"
    assert state.shutdown_requested.is_set()
