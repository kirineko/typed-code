"""Config reload and session model switch API tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from typed_code.service.app_state import AppState


@pytest.mark.asyncio
async def test_models_include_context_token_budget(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    res = await client.get("/v1/models", headers=auth_headers)
    assert res.status_code == 200
    models = res.json()["models"]
    assert models
    for m in models:
        assert "context_token_budget" in m
        assert isinstance(m["context_token_budget"], int)
        assert m["context_token_budget"] > 0
    deepseek = next(m for m in models if m["provider"] == "deepseek")
    assert deepseek["context_token_budget"] == 1_000_000
    sol = next((m for m in models if m["model_id"] == "gpt-5.6-sol"), None)
    if sol is not None:
        assert sol["context_token_budget"] == 272_000


@pytest.mark.asyncio
async def test_reload_config_secret_safe(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    res = await client.post("/v1/config/reload", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reloaded"] is True
    assert "providers" in body
    blob = res.text.lower()
    assert "sk-" not in blob
    assert "api_key" not in blob
    assert "server_token" not in blob or "missing" in blob


@pytest.mark.asyncio
async def test_update_session_model_idle(
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
    assert created.status_code == 200, created.text
    sid = created.json()["snapshot"]["session_id"]

    updated = await client.post(
        f"/v1/sessions/{sid}/model",
        headers=auth_headers,
        json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )
    assert updated.status_code == 200, updated.text
    snap = updated.json()
    assert snap["provider"] == "deepseek"
    assert snap["model"] == "deepseek-v4-flash"
    assert snap["phase"] == "idle"


@pytest.mark.asyncio
async def test_update_session_model_rejects_when_not_idle(
    client: AsyncClient,
    auth_headers: dict[str, str],
    api_env: tuple[AppState, Path, str],
) -> None:
    """Force non-idle phase via repository, then assert model switch conflicts."""
    state, ws, _token = api_env
    created = await client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={"workspace_path": str(ws), "provider": "cliproxy", "model": "gpt-5.6-sol"},
    )
    sid = created.json()["snapshot"]["session_id"]
    await state.repository.start_turn(sid, "hold run open")

    bad = await client.post(
        f"/v1/sessions/{sid}/model",
        headers=auth_headers,
        json={"provider": "deepseek", "model": "deepseek-v4-flash"},
    )
    assert bad.status_code in {409, 400, 422}, bad.text


@pytest.mark.asyncio
async def test_update_session_model_rejects_unknown(
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
    bad = await client.post(
        f"/v1/sessions/{sid}/model",
        headers=auth_headers,
        json={"provider": "cliproxy", "model": "does-not-exist-xyz"},
    )
    assert bad.status_code >= 400
