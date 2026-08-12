"""Native Responses web_search binding and public activity."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from tests.conformance.fake_responses_server import FakeResponsesState, create_fake_app
from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import EventType, ProviderName
from typed_code.protocol.events import ToolStartedData
from typed_code.providers.catalog import ModelCatalog
from typed_code.providers.factories import build_responses_model
from typed_code.runtime import AgentRuntime
from typed_code.runtime.native_tools import (
    web_search_call_summary,
    web_search_result_summary,
)


def _creds() -> Credentials:
    return Credentials(
        server_token=SecretStr("t"),
        deepseek_api_key=SecretStr("k"),
        cliproxy_api_key=SecretStr("k"),
        server_token_present=True,
        deepseek_availability=ProviderAvailability.AVAILABLE,
        cliproxy_availability=ProviderAvailability.AVAILABLE,
    )


def _request_tool_types(body: dict[str, object]) -> list[str]:
    tools = body.get("tools")
    if not isinstance(tools, list):
        return []
    types: list[str] = []
    for tool in tools:
        if isinstance(tool, dict) and isinstance(tool.get("type"), str):
            types.append(tool["type"])
    return types


@pytest.mark.asyncio
async def test_enabled_run_sends_web_search_tool(tmp_path: Path) -> None:
    state = FakeResponsesState(mode="text", model_ids=["gpt-5.6-terra"])
    app = create_fake_app(state)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        settings = Settings(
            data_dir=tmp_path / "data",
            cliproxy_base_url="http://test/v1",
        )
        catalog = ModelCatalog(settings=settings, credentials=_creds())
        await catalog.refresh_cliproxy(client=http)
        model = build_responses_model(
            catalog.resolve(ProviderName.CLIPROXY, "gpt-5.6-terra"),
            api_key="k",
            http_client=http,
        )
        db = await open_database(tmp_path / "db.sqlite")
        try:
            repo = SessionRepository(db)
            created = await repo.create_session(
                workspace_path=str(tmp_path / "missing-ws"),
                provider=ProviderName.CLIPROXY,
                model="gpt-5.6-terra",
            )
            runtime = AgentRuntime(
                repository=repo,
                catalog=catalog,
                settings=settings,
                model_override=model,
                enable_workspace_tools=False,
            )
            await runtime.run_turn(created.snapshot.session_id, "ping")
        finally:
            await db.close()

    assert state.bodies
    types = _request_tool_types(state.bodies[-1])
    assert "web_search" in types


@pytest.mark.asyncio
async def test_enabled_run_keeps_function_tools_with_web_search(tmp_path: Path) -> None:
    state = FakeResponsesState(mode="text", model_ids=["gpt-5.6-terra"])
    app = create_fake_app(state)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        settings = Settings(
            data_dir=tmp_path / "data",
            cliproxy_base_url="http://test/v1",
        )
        catalog = ModelCatalog(settings=settings, credentials=_creds())
        await catalog.refresh_cliproxy(client=http)
        model = build_responses_model(
            catalog.resolve(ProviderName.CLIPROXY, "gpt-5.6-terra"),
            api_key="k",
            http_client=http,
        )
        ws = tmp_path / "ws"
        ws.mkdir()
        db = await open_database(tmp_path / "db.sqlite")
        try:
            repo = SessionRepository(db)
            created = await repo.create_session(
                workspace_path=str(ws),
                provider=ProviderName.CLIPROXY,
                model="gpt-5.6-terra",
            )
            runtime = AgentRuntime(
                repository=repo,
                catalog=catalog,
                settings=settings,
                model_override=model,
            )
            await runtime.run_turn(created.snapshot.session_id, "ping")
        finally:
            await db.close()

    assert state.bodies
    types = _request_tool_types(state.bodies[-1])
    assert "web_search" in types
    assert "function" in types


@pytest.mark.asyncio
async def test_disabled_run_omits_web_search_tool(tmp_path: Path) -> None:
    state = FakeResponsesState(mode="text", model_ids=["gpt-5.6-terra"])
    app = create_fake_app(state)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        settings = Settings(
            data_dir=tmp_path / "data",
            cliproxy_base_url="http://test/v1",
            native_web_search=False,
        )
        catalog = ModelCatalog(settings=settings, credentials=_creds())
        await catalog.refresh_cliproxy(client=http)
        model = build_responses_model(
            catalog.resolve(ProviderName.CLIPROXY, "gpt-5.6-terra"),
            api_key="k",
            http_client=http,
        )
        db = await open_database(tmp_path / "db.sqlite")
        try:
            repo = SessionRepository(db)
            created = await repo.create_session(
                workspace_path=str(tmp_path / "ws"),
                provider=ProviderName.CLIPROXY,
                model="gpt-5.6-terra",
            )
            runtime = AgentRuntime(
                repository=repo,
                catalog=catalog,
                settings=settings,
                model_override=model,
            )
            await runtime.run_turn(created.snapshot.session_id, "ping")
        finally:
            await db.close()

    assert state.bodies
    assert "web_search" not in _request_tool_types(state.bodies[-1])


@pytest.mark.asyncio
async def test_web_search_stream_publishes_public_tool_activity(tmp_path: Path) -> None:
    state = FakeResponsesState(mode="web_search", model_ids=["gpt-5.6-terra"])
    app = create_fake_app(state)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        settings = Settings(
            data_dir=tmp_path / "data",
            cliproxy_base_url="http://test/v1",
        )
        catalog = ModelCatalog(settings=settings, credentials=_creds())
        await catalog.refresh_cliproxy(client=http)
        model = build_responses_model(
            catalog.resolve(ProviderName.CLIPROXY, "gpt-5.6-terra"),
            api_key="k",
            http_client=http,
        )
        db = await open_database(tmp_path / "db.sqlite")
        try:
            repo = SessionRepository(db)
            created = await repo.create_session(
                workspace_path=str(tmp_path / "ws"),
                provider=ProviderName.CLIPROXY,
                model="gpt-5.6-terra",
            )
            (tmp_path / "ws").mkdir()
            runtime = AgentRuntime(
                repository=repo,
                catalog=catalog,
                settings=settings,
                model_override=model,
                enable_workspace_tools=False,
            )
            turn = await runtime.run_turn(
                created.snapshot.session_id, "what is the latest release?"
            )
            events = await repo.list_events(created.snapshot.session_id, after=0)
            types = [event.type for event in events.events]
            assert EventType.TOOL_STARTED in types
            assert EventType.TOOL_COMPLETED in types
            started = next(
                event for event in events.events if event.type is EventType.TOOL_STARTED
            )
            assert isinstance(started.data, ToolStartedData)
            assert started.data.tool_name == "web_search"
            assert any(item.type == "tool_call" for item in turn.final.snapshot.transcript)
            assert any(item.type == "tool_result" for item in turn.final.snapshot.transcript)
            history = await repo.list_model_messages(created.snapshot.session_id)
            payload = "\n".join(record.payload_json for record in history)
            assert "builtin-tool-call" in payload
            assert "builtin-tool-return" in payload
            assert "web_search" in payload
        finally:
            await db.close()


def test_web_search_summaries_are_sanitized() -> None:
    assert web_search_call_summary({"query": "typed-code release"}) == "search typed-code release"
    assert web_search_call_summary({"queries": ["one", "two"]}) == "search one; two"
    assert web_search_result_summary({"status": "completed"}, ok=True) == "search completed"
    assert (
        web_search_result_summary(
            {"status": "completed", "sources": [{"url": "https://secret.example"}]},
            ok=True,
        )
        == "search completed (1 sources)"
    )
    assert "secret.example" not in web_search_result_summary(
        {"sources": [{"url": "https://secret.example"}]},
        ok=True,
    )
    assert web_search_result_summary({"status": "failed"}, ok=False) == "web search failed"
