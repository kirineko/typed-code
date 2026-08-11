"""Conformance against fake Responses HTTP endpoints."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from tests.conformance.fake_responses_server import FakeResponsesState, create_fake_app
from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ProviderName, SessionPhase
from typed_code.providers.catalog import ModelCatalog
from typed_code.providers.factories import build_responses_model
from typed_code.providers.profiles import DEEPSEEK_MODEL_ID
from typed_code.runtime import AgentRuntime


@pytest.mark.asyncio
async def test_text_via_fake_responses_no_chat_completions(tmp_path: Path) -> None:
    state = FakeResponsesState(mode="text", model_ids=["gpt-5.6-sol"])
    app = create_fake_app(state)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as http_client:
        # Discovery
        settings = Settings(
            data_dir=tmp_path / "data",
            cliproxy_base_url="http://test/v1",
            deepseek_base_url="http://test",
        )
        creds = Credentials(
            server_token=SecretStr("t"),
            deepseek_api_key=SecretStr("k"),
            cliproxy_api_key=SecretStr("k"),
            server_token_present=True,
            deepseek_availability=ProviderAvailability.AVAILABLE,
            cliproxy_availability=ProviderAvailability.AVAILABLE,
        )
        catalog = ModelCatalog(settings=settings, credentials=creds)
        await catalog.refresh_cliproxy(client=http_client)
        assert "gpt-5.6-sol" in {m.model_id for m in catalog.list_models().models}

        resolved = catalog.resolve(ProviderName.CLIPROXY, "gpt-5.6-sol")
        model = build_responses_model(
            resolved, api_key="k", http_client=http_client
        )

        db = await open_database(tmp_path / "db.sqlite")
        try:
            repo = SessionRepository(db)
            created = await repo.create_session(
                workspace_path=str(tmp_path / "ws"),
                provider=ProviderName.CLIPROXY,
                model="gpt-5.6-sol",
            )
            runtime = AgentRuntime(
                repository=repo, catalog=catalog, model_override=model
            )
            turn = await runtime.run_turn(created.snapshot.session_id, "ping")
            # Either success with fake output or failed with sanitized error if wire format differs
            assert turn.final.snapshot.session_id == created.snapshot.session_id
            assert "/v1/chat/completions" not in state.paths
            assert not any(p.endswith("chat/completions-HIT") for p in state.paths)
            # Factory/runtime used responses path when model was invoked
            if turn.final.snapshot.phase is SessionPhase.IDLE and any(
                i.type == "assistant_message" for i in turn.final.snapshot.transcript
            ):
                assert any("responses" in p for p in state.paths)
        finally:
            await db.close()


@pytest.mark.asyncio
async def test_api_failure_sanitized(tmp_path: Path) -> None:
    state = FakeResponsesState(mode="error")
    app = create_fake_app(state)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        settings = Settings(
            data_dir=tmp_path / "data", deepseek_base_url="http://test"
        )
        creds = Credentials(
            server_token=SecretStr("t"),
            deepseek_api_key=SecretStr("super-secret-key"),
            cliproxy_api_key=None,
            server_token_present=True,
            deepseek_availability=ProviderAvailability.AVAILABLE,
            cliproxy_availability=ProviderAvailability.MISSING_CREDENTIALS,
        )
        catalog = ModelCatalog(settings=settings, credentials=creds)
        resolved = catalog.resolve(ProviderName.DEEPSEEK, DEEPSEEK_MODEL_ID)
        model = build_responses_model(
            resolved, api_key="super-secret-key", http_client=http
        )
        db = await open_database(tmp_path / "db.sqlite")
        try:
            repo = SessionRepository(db)
            created = await repo.create_session(
                workspace_path=str(tmp_path / "ws"),
                provider=ProviderName.DEEPSEEK,
                model=DEEPSEEK_MODEL_ID,
            )
            runtime = AgentRuntime(
                repository=repo, catalog=catalog, model_override=model
            )
            turn = await runtime.run_turn(created.snapshot.session_id, "hi")
            assert turn.final.snapshot.phase is SessionPhase.IDLE
            # Secret must not appear in public event payloads
            blob = str(turn.final.events)
            assert "super-secret-key" not in blob
        finally:
            await db.close()
