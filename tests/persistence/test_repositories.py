"""Repository atomicity, revision/sequence monotonicity."""

from __future__ import annotations

import asyncio

import pytest

from typed_code.domain import DomainConflict
from typed_code.domain.transitions import TransitionResult
from typed_code.persistence import SessionRepository
from typed_code.protocol.common import ProviderName, SessionPhase
from typed_code.protocol.errors import ErrorCode, StructuredError


@pytest.mark.asyncio
async def test_create_and_start_turn_monotonic(repo: SessionRepository) -> None:
    created = await repo.create_session(
        workspace_path="/tmp/ws",
        provider=ProviderName.CLIPROXY,
        model="m1",
    )
    assert created.snapshot.revision == 1
    assert created.snapshot.latest_event_sequence == 0
    assert created.events == []

    turned = await repo.start_turn(created.snapshot.session_id, "hello")
    assert turned.snapshot.revision == 2
    assert turned.snapshot.phase is SessionPhase.RUNNING
    assert turned.snapshot.latest_event_sequence == 2
    assert [e.sequence for e in turned.events] == [1, 2]
    last = turned.snapshot.transcript[-1]
    assert last.type == "user_message"
    assert last.text == "hello"  # type: ignore[union-attr]

    completed = await repo.complete_run(created.snapshot.session_id)
    assert completed.snapshot.revision == 3
    assert completed.snapshot.phase is SessionPhase.IDLE
    assert completed.snapshot.active_run is None
    assert completed.snapshot.latest_event_sequence == 3


@pytest.mark.asyncio
async def test_concurrent_turn_conflict(repo: SessionRepository, seeded_session: str) -> None:
    await repo.start_turn(seeded_session, "first")
    with pytest.raises(DomainConflict):
        await repo.start_turn(seeded_session, "second")


@pytest.mark.asyncio
async def test_concurrent_session_writes_are_serialized(
    repo: SessionRepository,
) -> None:
    async def create(index: int):
        return await repo.create_session(
            workspace_path=f"/tmp/ws-{index}",
            provider=ProviderName.CLIPROXY,
            model="m1",
        )

    created = await asyncio.gather(create(1), create(2))
    assert len({item.snapshot.session_id for item in created}) == 2
    assert all(item.snapshot.revision == 1 for item in created)


@pytest.mark.asyncio
async def test_read_waits_for_rollback_instead_of_observing_uncommitted_state(
    repo: SessionRepository,
) -> None:
    wrote = asyncio.Event()
    release = asyncio.Event()
    original = repo._write_transition

    async def fail_after_write(
        result: TransitionResult,
        *,
        is_new_session: bool = False,
    ) -> None:
        await original(result, is_new_session=is_new_session)
        wrote.set()
        await release.wait()
        raise RuntimeError("forced rollback")

    object.__setattr__(repo, "_write_transition", fail_after_write)
    writer = asyncio.create_task(
        repo.create_session(
            workspace_path="/tmp/uncommitted",
            provider=ProviderName.CLIPROXY,
            model="m1",
        )
    )
    try:
        await wrote.wait()
        reader = asyncio.create_task(repo.list_sessions())
        await asyncio.sleep(0)
        assert reader.done() is False
        release.set()
        with pytest.raises(RuntimeError, match="forced rollback"):
            await writer
        assert await reader == []
    finally:
        release.set()
        object.__setattr__(repo, "_write_transition", original)

@pytest.mark.asyncio
async def test_transaction_rollback_leaves_revision_unchanged(
    repo: SessionRepository, seeded_session: str
) -> None:
    before = await repo.get_snapshot(seeded_session)
    # Force failure after BEGIN by using an invalid mutation path: monkeypatch write.
    original = repo._write_transition

    async def boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("forced failure")

    object.__setattr__(repo, "_write_transition", boom)
    try:
        with pytest.raises(RuntimeError, match="forced failure"):
            await repo.start_turn(seeded_session, "will fail")
    finally:
        object.__setattr__(repo, "_write_transition", original)

    after = await repo.get_snapshot(seeded_session)
    assert after.revision == before.revision
    assert after.latest_event_sequence == before.latest_event_sequence
    assert after.phase is SessionPhase.IDLE


@pytest.mark.asyncio
async def test_fail_run_records_error(repo: SessionRepository, seeded_session: str) -> None:
    await repo.start_turn(seeded_session, "do work")
    failed = await repo.fail_run(
        seeded_session,
        StructuredError(code=ErrorCode.RUN_FAILED, message="provider down"),
    )
    assert failed.snapshot.phase is SessionPhase.IDLE
    assert failed.events[-1].type.value == "run.failed"
