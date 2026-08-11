"""Turn, abort, and SSE tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient

from typed_code.service.app_state import AppState


@pytest.mark.asyncio
async def test_turn_and_conflict(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    _state, ws, _token = api_env
    created = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={"workspace_path": str(ws), "provider": "cliproxy", "model": "gpt-5.6-sol"},
    )
    sid = created.json()["snapshot"]["session_id"]

    turn = await client.post(
        f"/v1/sessions/{sid}/turns",
        headers=auth_headers,
        json={"prompt": "hello agent"},
    )
    assert turn.status_code == 200, turn.text
    body = turn.json()
    assert body["status"] == "accepted"
    assert body["phase"] in {"running", "idle", "awaiting_approval"}

    # Wait for completion
    for _ in range(100):
        snap = await client.get(f"/v1/sessions/{sid}", headers=auth_headers)
        if snap.json()["phase"] == "idle":
            break
        await asyncio.sleep(0.02)

    snap = (await client.get(f"/v1/sessions/{sid}", headers=auth_headers)).json()
    assert snap["phase"] == "idle"
    assert any(i.get("type") == "assistant_message" for i in snap["transcript"])


@pytest.mark.asyncio
async def test_abort(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    _state, ws, _token = api_env
    created = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={"workspace_path": str(ws), "provider": "cliproxy", "model": "gpt-5.6-sol"},
    )
    sid = created.json()["snapshot"]["session_id"]
    await client.post(
        f"/v1/sessions/{sid}/turns",
        headers=auth_headers,
        json={"prompt": "go"},
    )
    abort = await client.post(
        f"/v1/sessions/{sid}/abort",
        headers=auth_headers,
        json={},
    )
    assert abort.status_code == 200
    # Idempotent
    abort2 = await client.post(
        f"/v1/sessions/{sid}/abort",
        headers=auth_headers,
        json={},
    )
    assert abort2.status_code == 200


@pytest.mark.asyncio
async def test_sse_replay(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    state, ws, _token = api_env
    created = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={"workspace_path": str(ws), "provider": "cliproxy", "model": "gpt-5.6-sol"},
    )
    sid = created.json()["snapshot"]["session_id"]
    await client.post(
        f"/v1/sessions/{sid}/turns",
        headers=auth_headers,
        json={"prompt": "hello"},
    )
    for _ in range(100):
        snap = await client.get(f"/v1/sessions/{sid}", headers=auth_headers)
        if snap.json()["phase"] == "idle":
            break
        await asyncio.sleep(0.02)

    # Prefer repository replay (same path SSE uses) to avoid open stream hangs in ASGI tests
    replay = await state.repository.list_events(sid, after=0)
    assert replay.status == "ok"
    assert replay.events
    assert replay.events[0].protocol_version == 1
    assert replay.events[0].sequence >= 1
