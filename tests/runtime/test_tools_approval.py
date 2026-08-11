"""Workspace tools + approval gating via AgentRuntime."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_ai.models.test import TestModel

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ApprovalDecision, ProviderName, SessionPhase
from typed_code.providers.catalog import ModelCatalog
from typed_code.runtime import AgentRuntime


def _runtime(tmp_path: Path, repo: SessionRepository, *, auto: bool) -> AgentRuntime:
    settings = Settings(data_dir=tmp_path / "data", bash_executable="/bin/bash")
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
    return AgentRuntime(
        repository=repo,
        catalog=catalog,
        settings=settings,
        model_override=TestModel(call_tools=["write_file"]),
        enable_workspace_tools=True,
        auto_approve_mutations=auto,
    )

@pytest.mark.asyncio
async def test_reload_settings_rebuilds_cached_workspace_backend(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = await open_database(tmp_path / "settings.db")
    try:
        repo = SessionRepository(db)
        runtime = _runtime(tmp_path, repo, auto=False)
        before = await runtime._backend_for(str(ws))
        settings = Settings(
            data_dir=tmp_path / "new-data",
            bash_executable="/bin/bash",
            bash_max_stdout_bytes=1234,
        )

        runtime.reload_settings(settings)
        after = await runtime._backend_for(str(ws))

        assert after is not before
        assert runtime.settings is settings
        assert after.settings.bash_max_stdout_bytes == 1234
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_auto_approve_write(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = await open_database(tmp_path / "t.db")
    try:
        repo = SessionRepository(db)
        settings = Settings(data_dir=tmp_path / "data")
        created = await repo.create_session(
            workspace_path=str(ws),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        runtime = _runtime(tmp_path, repo, auto=True)
        turn = await runtime.run_turn(created.snapshot.session_id, "write a file")
        assert turn.awaiting_approval is False
        assert turn.final.snapshot.phase is SessionPhase.IDLE
        # TestModel may write path a — check something was created or run completed
        assert turn.final.snapshot.transcript
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_manual_approval_resume(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = await open_database(tmp_path / "t.db")
    try:
        repo = SessionRepository(db)
        settings = Settings(data_dir=tmp_path / "data")
        created = await repo.create_session(
            workspace_path=str(ws),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        runtime = _runtime(tmp_path, repo, auto=False)
        turn = await runtime.run_turn(created.snapshot.session_id, "write a file")
        assert turn.awaiting_approval is True
        assert turn.final.snapshot.phase is SessionPhase.AWAITING_APPROVAL
        assert turn.final.snapshot.pending_approvals

        approval_id = turn.final.snapshot.pending_approvals[0].approval_id
        resumed = await runtime.resume_after_approval(
            created.snapshot.session_id,
            approval_id=approval_id,
            decision=ApprovalDecision.APPROVE,
        )
        assert resumed.awaiting_approval is False
        assert resumed.final.snapshot.phase is SessionPhase.IDLE
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_reject_approval(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = await open_database(tmp_path / "t.db")
    try:
        repo = SessionRepository(db)
        settings = Settings(data_dir=tmp_path / "data")
        created = await repo.create_session(
            workspace_path=str(ws),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        runtime = _runtime(tmp_path, repo, auto=False)
        turn = await runtime.run_turn(created.snapshot.session_id, "write")
        approval_id = turn.final.snapshot.pending_approvals[0].approval_id
        resumed = await runtime.resume_after_approval(
            created.snapshot.session_id,
            approval_id=approval_id,
            decision=ApprovalDecision.REJECT,
        )
        assert resumed.final.snapshot.phase is SessionPhase.IDLE
        # No writes expected when rejected before execution
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_fabricated_approval_rejected(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    db = await open_database(tmp_path / "t.db")
    try:
        repo = SessionRepository(db)
        settings = Settings(data_dir=tmp_path / "data")
        created = await repo.create_session(
            workspace_path=str(ws),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        runtime = _runtime(tmp_path, repo, auto=False)
        await runtime.run_turn(created.snapshot.session_id, "write")
        from typed_code.domain.errors import DomainConflict

        with pytest.raises(DomainConflict):
            await runtime.resume_after_approval(
                created.snapshot.session_id,
                approval_id="does-not-exist",
                decision=ApprovalDecision.APPROVE,
            )
    finally:
        await db.close()
