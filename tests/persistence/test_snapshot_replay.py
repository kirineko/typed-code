"""Snapshot reconstruction and event replay/reset."""

from __future__ import annotations

import pytest

from typed_code.persistence import SessionRepository
from typed_code.protocol.common import ApprovalDecision, ProviderName, SessionPhase


@pytest.mark.asyncio
async def test_snapshot_after_multi_step_flow(repo: SessionRepository) -> None:
    created = await repo.create_session(
        workspace_path="/tmp/proj",
        provider=ProviderName.DEEPSEEK,
        model="deepseek-v4-flash",
    )
    sid = created.snapshot.session_id

    await repo.start_turn(sid, "please edit")
    await repo.request_approval(
        sid,
        tool_call_id="tc1",
        tool_name="edit",
        summary="edit main.py",
        request_json='{"path":"main.py"}',
    )
    snap = await repo.get_snapshot(sid)
    assert snap.phase is SessionPhase.AWAITING_APPROVAL
    assert len(snap.pending_approvals) == 1
    assert snap.pending_approvals[0].tool_name == "edit"
    assert any(i.type == "user_message" for i in snap.transcript)

    await repo.resolve_approval(
        sid,
        approval_id=snap.pending_approvals[0].approval_id,
        decision=ApprovalDecision.APPROVE,
    )
    await repo.complete_run(sid)
    final = await repo.get_snapshot(sid)
    assert final.phase is SessionPhase.IDLE
    assert final.pending_approvals == []
    assert final.revision >= 5


@pytest.mark.asyncio
async def test_event_replay_from_after(repo: SessionRepository, seeded_session: str) -> None:
    turned = await repo.start_turn(seeded_session, "one")
    assert len(turned.events) == 2

    replay_all = await repo.list_events(seeded_session, after=0)
    assert replay_all.status == "ok"
    assert [e.sequence for e in replay_all.events] == [1, 2]

    replay_partial = await repo.list_events(seeded_session, after=1)
    assert replay_partial.status == "ok"
    assert [e.sequence for e in replay_partial.events] == [2]

    replay_empty = await repo.list_events(seeded_session, after=2)
    assert replay_empty.status == "ok"
    assert replay_empty.events == []


@pytest.mark.asyncio
async def test_replay_reset_when_window_expired(
    repo: SessionRepository, seeded_session: str
) -> None:
    # retention is 5; produce more than 5 events via multiple turns
    for i in range(4):
        await repo.start_turn(seeded_session, f"turn {i}")
        await repo.complete_run(seeded_session)

    # each turn: 2 events start + 1 complete = 3; 4 turns => 12 events; keep last 5
    snap = await repo.get_snapshot(seeded_session)
    assert snap.latest_event_sequence == 12

    reset = await repo.list_events(seeded_session, after=1)
    assert reset.status == "reset"
    assert reset.events == []
    assert reset.snapshot is not None
    assert reset.snapshot.session_id == seeded_session
    assert reset.snapshot.latest_event_sequence == 12

    ok = await repo.list_events(seeded_session, after=8)
    assert ok.status == "ok"
    assert ok.events
    assert ok.events[0].sequence == 9
