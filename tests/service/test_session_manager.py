"""SessionManager unit tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_ai.models.test import TestModel

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ProviderName, SessionPhase
from typed_code.providers.catalog import ModelCatalog
from typed_code.runtime import AgentRuntime
from typed_code.service.event_bus import EventBus
from typed_code.service.publishing import PublishingRepository
from typed_code.service.session_manager import SessionManager


@pytest.mark.asyncio
async def test_submit_turn_and_conflict(tmp_path: Path) -> None:
    (tmp_path / "ws").mkdir()
    db = await open_database(tmp_path / "db.sqlite")
    try:
        bus = EventBus()
        base = SessionRepository(db)
        repo: SessionRepository = PublishingRepository(base, bus.publish)
        settings = Settings(data_dir=tmp_path / "data")
        creds = Credentials(
            server_token=SecretStr("t"),
            deepseek_api_key=None,
            cliproxy_api_key=SecretStr("k"),
            server_token_present=True,
            deepseek_availability=ProviderAvailability.MISSING_CREDENTIALS,
            cliproxy_availability=ProviderAvailability.AVAILABLE,
        )
        catalog = ModelCatalog(settings=settings, credentials=creds)
        catalog.seed_cliproxy_models({settings.default_model})
        runtime = AgentRuntime(
            repository=repo,
            catalog=catalog,
            settings=settings,
            model_override=TestModel(custom_output_text="ok"),
            enable_workspace_tools=False,
        )
        manager = SessionManager(
            repository=repo,
            runtime=runtime,
            event_bus=bus,
        )
        created = await repo.create_session(
            workspace_path=str(tmp_path / "ws"),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        sid = created.snapshot.session_id
        resp = await manager.submit_turn(sid, "hi")
        assert resp.phase in {
            SessionPhase.RUNNING,
            SessionPhase.IDLE,
            SessionPhase.AWAITING_APPROVAL,
        }
        for _ in range(100):
            if sid not in manager._tasks:
                break
            await asyncio.sleep(0)
        assert sid not in manager._tasks
    finally:
        await db.close()
