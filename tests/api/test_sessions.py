"""Session HTTP routes."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from typed_code.service.app_state import AppState


@pytest.mark.asyncio
async def test_create_list_get_session(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    _state, ws, _token = api_env
    create = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={"workspace_path": str(ws), "provider": "cliproxy", "model": "gpt-5.6-sol"},
    )
    assert create.status_code == 200, create.text
    snap = create.json()["snapshot"]
    sid = snap["session_id"]
    assert snap["phase"] == "idle"

    listed = await client.get("/v1/sessions", headers=auth_headers)
    assert listed.status_code == 200
    assert any(s["session_id"] == sid for s in listed.json()["sessions"])

    got = await client.get(f"/v1/sessions/{sid}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["session_id"] == sid


@pytest.mark.asyncio
async def test_create_missing_workspace(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={"workspace_path": "/no/such/dir-xyz", "provider": "cliproxy"},
    )
    assert resp.status_code in {400, 422}
