"""AgentRuntime text turn with TestModel."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_ai import ThinkingPart, ThinkingPartDelta
from pydantic_ai.models.test import TestModel

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ProviderName, SessionPhase
from typed_code.protocol.events import (
    MessageAssistantDeltaData,
    MessageAssistantDoneData,
)
from typed_code.providers.catalog import ModelCatalog
from typed_code.providers.profiles import DEEPSEEK_MODEL_ID
from typed_code.providers.settings_normalize import RunSettingRequest
from typed_code.runtime import AgentRuntime
from typed_code.runtime.adapter import _prefer_thinking_text, _thinking_text
from typed_code.runtime.thinking import apply_thinking_delta


def test_deepseek_provider_reasoning_is_displayable() -> None:
    part = ThinkingPart(
        content="",
        provider_name="deepseek",
        provider_details={"raw_content": ["inspect ", "the workspace first"]},
    )

    assert _thinking_text(part) == "inspect the workspace first"


def test_thinking_text_prefers_longer_native_payload() -> None:
    part = ThinkingPart(
        content="用",
        provider_name="deepseek",
        provider_details={"raw_content": ["用户先确认角色再搜索"]},
    )

    assert _thinking_text(part) == "用户先确认角色再搜索"


def test_apply_thinking_delta_reads_provider_raw_content() -> None:
    part = ThinkingPart(
        content="用",
        provider_name="deepseek",
        provider_details={"raw_content": ["用"]},
    )

    def update_raw(existing: dict[str, object] | None) -> dict[str, object]:
        details = dict(existing or {})
        raw_value = details.get("raw_content", [])
        raw = list(raw_value) if isinstance(raw_value, list) else [""]
        if not raw:
            raw = [""]
        raw[0] = str(raw[0]) + "户先确认"
        details["raw_content"] = raw
        return details

    updated, piece = apply_thinking_delta(
        part, ThinkingPartDelta(provider_details=update_raw)
    )

    assert piece == "户先确认"
    assert _thinking_text(updated) == "用户先确认"


def test_prefer_thinking_text_keeps_longer_streamed_accumulation() -> None:
    part = ThinkingPart(content="用户", provider_name="deepseek")

    assert (
        _prefer_thinking_text(part, "用户先确认角色再搜索")
        == "用户先确认角色再搜索"
    )
    assert _prefer_thinking_text(part, "") == "用户"


@pytest.mark.asyncio
async def test_run_turn_text_with_test_model(tmp_path: Path) -> None:
    db = await open_database(tmp_path / "t.db")
    try:
        repo = SessionRepository(db)
        settings = Settings(data_dir=tmp_path / "data")
        creds = Credentials(
            server_token=SecretStr("t"),
            deepseek_api_key=SecretStr("k"),
            cliproxy_api_key=SecretStr("k"),
            server_token_present=True,
            deepseek_availability=ProviderAvailability.AVAILABLE,
            cliproxy_availability=ProviderAvailability.AVAILABLE,
        )
        catalog = ModelCatalog(settings=settings, credentials=creds)
        catalog.seed_cliproxy_models({settings.default_model})

        (tmp_path / "ws").mkdir()
        created = await repo.create_session(
            workspace_path=str(tmp_path / "ws"),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        runtime = AgentRuntime(
            repository=repo,
            catalog=catalog,
            model_override=TestModel(custom_output_text="assistant says hi"),
            enable_workspace_tools=False,
        )
        turn = await runtime.run_turn(created.snapshot.session_id, "hello agent")
        assert turn.final.snapshot.phase is SessionPhase.IDLE
        assert any(
            getattr(i, "text", None) == "assistant says hi"
            for i in turn.final.snapshot.transcript
            if i.type == "assistant_message"
        )
        msgs = await repo.list_model_messages(created.snapshot.session_id)
        assert any(m.payload_json.lstrip().startswith("[") for m in msgs)
        replay = await repo.list_events(created.snapshot.session_id, after=0)
        streamed = [
            event
            for event in replay.events
            if event.type.value
            in {"message.assistant.delta", "message.assistant.done"}
        ]
        deltas = [
            event.data
            for event in streamed[:-1]
            if isinstance(event.data, MessageAssistantDeltaData)
        ]
        done = streamed[-1].data
        assert isinstance(done, MessageAssistantDoneData)
        assert len(deltas) == len(streamed) - 1
        assert len(deltas) > 1
        assert "".join(data.delta for data in deltas) == "assistant says hi"
        assert deltas[0].message_id == done.message_id
        assert turn.effective_settings.send_previous_response_id is False
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_reject_image_before_run(tmp_path: Path) -> None:
    db = await open_database(tmp_path / "t.db")
    try:
        repo = SessionRepository(db)
        settings = Settings(data_dir=tmp_path / "data")
        creds = Credentials(
            server_token=SecretStr("t"),
            deepseek_api_key=SecretStr("k"),
            cliproxy_api_key=None,
            server_token_present=True,
            deepseek_availability=ProviderAvailability.AVAILABLE,
            cliproxy_availability=ProviderAvailability.MISSING_CREDENTIALS,
        )
        catalog = ModelCatalog(settings=settings, credentials=creds)
        (tmp_path / "ws").mkdir()
        created = await repo.create_session(
            workspace_path=str(tmp_path / "ws"),
            provider=ProviderName.DEEPSEEK,
            model=DEEPSEEK_MODEL_ID,
        )
        runtime = AgentRuntime(
            repository=repo,
            catalog=catalog,
            model_override=TestModel(custom_output_text="x"),
            enable_workspace_tools=False,
        )
        from typed_code.domain.errors import DomainValidationError

        with pytest.raises(DomainValidationError):
            await runtime.run_turn(
                created.snapshot.session_id,
                "hi",
                setting_request=RunSettingRequest(image_input=True),
            )
        # failed or still idle without corrupt active run after validation failure
        snap = await repo.get_snapshot(created.snapshot.session_id)
        assert snap.phase is SessionPhase.IDLE
    finally:
        await db.close()
