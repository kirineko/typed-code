"""First-party cancellation idempotency."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_ai.models.test import TestModel

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ProviderName, RunStatus, SessionPhase
from typed_code.providers.catalog import ModelCatalog
from typed_code.runtime import AgentRuntime


@pytest.mark.asyncio
async def test_cancel_active_and_repeat(tmp_path: Path) -> None:
    db = await open_database(tmp_path / "t.db")
    try:
        repo = SessionRepository(db)
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
        created = await repo.create_session(
            workspace_path=str(tmp_path / "ws"),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        sid = created.snapshot.session_id
        await repo.start_turn(sid, "running")
        runtime = AgentRuntime(
            repository=repo,
            catalog=catalog,
            model_override=TestModel(custom_output_text="nope"),
        )
        cancelled = await runtime.cancel(sid)
        assert cancelled.snapshot.phase is SessionPhase.IDLE

        # Idempotent second cancel
        again = await runtime.cancel(sid)
        assert again.snapshot.phase is SessionPhase.IDLE

        # Run row terminal cancelled
        cur = await db.connection.execute(
            "SELECT status FROM runs WHERE session_id = ? ORDER BY started_at DESC LIMIT 1",
            (sid,),
        )
        row = await cur.fetchone()
        assert row is not None
        assert row["status"] == RunStatus.CANCELLED.value
    finally:
        await db.close()
