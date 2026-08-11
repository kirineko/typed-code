"""Provider usage checkpoint persistence for hybrid token estimates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr
from pydantic_ai.models.test import TestModel

from typed_code.config.credentials import Credentials, ProviderAvailability
from typed_code.config.settings import Settings
from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ProviderName
from typed_code.providers.catalog import ModelCatalog
from typed_code.runtime import AgentRuntime


@pytest.mark.asyncio
async def test_finish_turn_persists_usage_checkpoint(tmp_path: Path) -> None:
    db = await open_database(tmp_path / "u.db")
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
        (tmp_path / "ws").mkdir()
        created = await repo.create_session(
            workspace_path=str(tmp_path / "ws"),
            provider=ProviderName.CLIPROXY,
            model=settings.default_model,
        )
        runtime = AgentRuntime(
            repository=repo,
            catalog=catalog,
            model_override=TestModel(custom_output_text="done"),
            enable_workspace_tools=False,
        )
        await runtime.run_turn(created.snapshot.session_id, "hello")

        checkpoint = await repo.get_context_usage_checkpoint(created.snapshot.session_id)
        assert checkpoint is not None
        assert checkpoint.tokens > 0
        assert checkpoint.message_count >= 1

        # Columns present on session row
        cur = await db.connection.execute(
            "SELECT last_usage_tokens, last_usage_message_count FROM sessions WHERE id = ?",
            (created.snapshot.session_id,),
        )
        row = await cur.fetchone()
        assert row is not None
        assert row["last_usage_tokens"] == checkpoint.tokens
        assert row["last_usage_message_count"] == checkpoint.message_count
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_compaction_adjusts_checkpoint_prefix(tmp_path: Path) -> None:
    db = await open_database(tmp_path / "c.db")
    try:
        repo = SessionRepository(db)
        created = await repo.create_session(
            workspace_path=str(tmp_path / "ws"),
            provider=ProviderName.CLIPROXY,
            model="m",
        )
        sid = created.snapshot.session_id

        # Seed PAI messages + checkpoint covering first 4
        payloads = [
            json.dumps([{"kind": "request", "parts": [{"content": f"u{i}" * 20}]}])
            for i in range(6)
        ]
        from typed_code.compaction.compact import ModelMessageRecord

        records = [
            ModelMessageRecord(
                id=f"m{i}",
                session_id=sid,
                run_id=None,
                position=i + 1,
                role="user",
                payload_json=payloads[i],
                created_at="t",
            )
            for i in range(6)
        ]
        await repo.replace_model_messages(
            sid,
            records,
            archive_reason="seed",
            archived_payload_json="[]",
        )
        await db.connection.execute(
            """
            UPDATE sessions
            SET last_usage_tokens = 100, last_usage_message_count = 4
            WHERE id = ?
            """,
            (sid,),
        )
        await db.connection.commit()

        kept = records[2:]  # drop 2 prefix
        await repo.replace_model_messages(
            sid,
            kept,
            archive_reason="context_budget",
            archived_payload_json="[]",
            removed_prefix_count=2,
        )
        checkpoint = await repo.get_context_usage_checkpoint(sid)
        assert checkpoint is not None
        assert checkpoint.tokens == 100
        assert checkpoint.message_count == 2  # 4 - 2
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_migration_adds_usage_columns(tmp_path: Path) -> None:
    db = await open_database(tmp_path / "mig.db")
    try:
        cur = await db.connection.execute("PRAGMA table_info(sessions)")
        cols = {row[1] for row in await cur.fetchall()}
        assert "last_usage_tokens" in cols
        assert "last_usage_message_count" in cols

        cur = await db.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        versions = [int(r[0]) for r in await cur.fetchall()]
        assert versions == [1, 2]
    finally:
        await db.close()
