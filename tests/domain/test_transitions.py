"""Pure domain transition rules."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from typed_code.domain import (
    DomainConflict,
    DomainValidationError,
    cancel_run,
    complete_run,
    create_session,
    fail_run,
    interrupt_run,
    request_approval,
    resolve_approval,
    start_turn,
    update_session_model,
)
from typed_code.protocol.common import (
    ApprovalDecision,
    EventType,
    ProviderName,
    RunStatus,
    SessionPhase,
)
from typed_code.protocol.errors import ErrorCode, StructuredError

FIXED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _clock() -> datetime:
    return FIXED


def _session():
    return create_session(
        workspace_path="/tmp/ws",
        provider=ProviderName.CLIPROXY,
        model="gpt-5.6-sol",
        clock=_clock,
        session_id="session-1",
    ).session


def test_create_session_starts_idle_revision_one() -> None:
    result = create_session(
        workspace_path="/tmp/ws",
        provider=ProviderName.DEEPSEEK,
        model="deepseek-v4-flash",
        clock=_clock,
    )
    assert result.session.phase is SessionPhase.IDLE
    assert result.session.revision == 1
    assert result.session.latest_event_sequence == 0
    assert result.events == []


def test_start_turn_idle_to_running() -> None:
    session = _session()
    result = start_turn(session, "  hello world  ", clock=_clock, run_id="run-1")
    assert result.session.phase is SessionPhase.RUNNING
    assert result.session.revision == 2
    assert result.session.active_run is not None
    assert result.session.active_run.run_id == "run-1"
    assert result.session.active_run.status is RunStatus.RUNNING
    last = result.session.transcript[-1]
    assert last.type == "user_message"
    assert last.text == "hello world"  # type: ignore[union-attr]
    types = [e.type for e in result.events]
    assert types == [EventType.RUN_STARTED, EventType.MESSAGE_USER]


def test_start_turn_conflict_when_active() -> None:
    session = start_turn(_session(), "first", clock=_clock).session
    with pytest.raises(DomainConflict):
        start_turn(session, "second", clock=_clock)


def test_complete_run_clears_active() -> None:
    session = start_turn(_session(), "go", clock=_clock, run_id="run-1").session
    result = complete_run(session, clock=_clock)
    assert result.session.phase is SessionPhase.IDLE
    assert result.session.active_run is None
    assert result.session.revision == 3
    assert result.updated_run is not None
    assert result.updated_run.status is RunStatus.COMPLETED
    assert result.events[0].type is EventType.RUN_COMPLETED


def test_fail_and_interrupt_and_cancel() -> None:
    base = _session()

    failed = fail_run(
        start_turn(base, "x", clock=_clock, run_id="r1").session,
        error=StructuredError(code=ErrorCode.RUN_FAILED, message="boom"),
        clock=_clock,
    )
    assert failed.updated_run is not None
    assert failed.updated_run.status is RunStatus.FAILED

    cancelled = cancel_run(
        start_turn(base, "x", clock=_clock, run_id="r2").session,
        clock=_clock,
    )
    assert cancelled.updated_run is not None
    assert cancelled.updated_run.status is RunStatus.CANCELLED

    interrupted = interrupt_run(
        start_turn(base, "x", clock=_clock, run_id="r3").session,
        clock=_clock,
    )
    assert interrupted.updated_run is not None
    assert interrupted.updated_run.status is RunStatus.INTERRUPTED
    assert any(i.type == "system_notice" for i in interrupted.transcript_items)


def test_approval_flow() -> None:
    session = start_turn(_session(), "edit please", clock=_clock, run_id="run-1").session
    requested = request_approval(
        session,
        tool_call_id="tc1",
        tool_name="edit",
        summary="edit file",
        request_json='{"path":"a.py"}',
        clock=_clock,
        approval_id="appr-1",
    )
    assert requested.session.phase is SessionPhase.AWAITING_APPROVAL
    assert requested.session.active_run is not None
    assert requested.session.active_run.status is RunStatus.AWAITING_APPROVAL

    with pytest.raises(DomainConflict):
        start_turn(requested.session, "another", clock=_clock)

    resolved = resolve_approval(
        requested.session,
        approval_id="appr-1",
        decision=ApprovalDecision.APPROVE,
        clock=_clock,
    )
    assert resolved.session.phase is SessionPhase.RUNNING
    assert resolved.session.pending_approvals == []
    assert resolved.events[0].type is EventType.APPROVAL_RESOLVED


def test_empty_prompt_rejected() -> None:
    with pytest.raises(DomainValidationError):
        start_turn(_session(), "   ", clock=_clock)


def test_update_session_model_idle() -> None:
    session = _session()
    updated = update_session_model(
        session,
        provider=ProviderName.DEEPSEEK,
        model="deepseek-v4-flash",
        clock=_clock,
    )
    assert updated.session.provider is ProviderName.DEEPSEEK
    assert updated.session.model == "deepseek-v4-flash"
    assert updated.session.revision == session.revision + 1
    assert updated.session.phase is SessionPhase.IDLE
    assert updated.events[0].type is EventType.SESSION_MODEL_CHANGED
    assert any(i.type.value == "system_notice" for i in updated.session.transcript)


def test_update_session_model_rejects_when_running() -> None:
    started = start_turn(_session(), "go", clock=_clock)
    with pytest.raises(DomainConflict):
        update_session_model(
            started.session,
            provider=ProviderName.DEEPSEEK,
            model="deepseek-v4-flash",
            clock=_clock,
        )
