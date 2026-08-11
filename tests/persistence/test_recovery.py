"""Startup recovery for abandoned non-terminal runs."""

from __future__ import annotations

from pathlib import Path

import pytest

from typed_code.persistence import SessionRepository, open_database
from typed_code.protocol.common import ProviderName, RunStatus, SessionPhase


@pytest.mark.asyncio
async def test_recover_abandoned_runs_marks_interrupted(tmp_path: Path) -> None:
    path = tmp_path / "recover.db"
    db = await open_database(path)
    try:
        repo = SessionRepository(db, event_retention_count=100)
        created = await repo.create_session(
            workspace_path="/tmp/ws",
            provider=ProviderName.CLIPROXY,
            model="m1",
        )
        sid = created.snapshot.session_id
        await repo.start_turn(sid, "still running")
        mid = await repo.get_snapshot(sid)
        assert mid.phase is SessionPhase.RUNNING
        assert mid.active_run is not None
        run_id = mid.active_run.run_id
        assert mid.transcript  # history present
        transcript_len = len(mid.transcript)
    finally:
        await db.close()

    # Re-open as a new process would
    db2 = await open_database(path)
    try:
        repo2 = SessionRepository(db2, event_retention_count=100)
        recovered = await repo2.recover_abandoned_runs()
        assert len(recovered) == 1
        snap = recovered[0].snapshot
        assert snap.session_id == sid
        assert snap.phase is SessionPhase.IDLE
        assert snap.active_run is None
        assert len(snap.transcript) >= transcript_len  # preserved + notice

        # Run row is interrupted
        cursor = await db2.connection.execute(
            "SELECT status FROM runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["status"] == RunStatus.INTERRUPTED.value

        # New turn is allowed
        again = await repo2.start_turn(sid, "resume work")
        assert again.snapshot.phase is SessionPhase.RUNNING
    finally:
        await db2.close()


@pytest.mark.asyncio
async def test_recover_is_noop_when_all_terminal(
    repo: SessionRepository, seeded_session: str
) -> None:
    await repo.start_turn(seeded_session, "done soon")
    await repo.complete_run(seeded_session)
    recovered = await repo.recover_abandoned_runs()
    assert recovered == []
