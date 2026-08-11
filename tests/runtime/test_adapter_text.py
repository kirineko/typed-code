"""AgentRuntime text turn with TestModel."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_ai.models.test import TestModel

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ProviderName, SessionPhase
from typed_code.providers.catalog import ModelCatalog
from typed_code.providers.profiles import DEEPSEEK_MODEL_ID
from typed_code.providers.settings_normalize import RunSettingRequest
from typed_code.runtime import AgentRuntime


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
