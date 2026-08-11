"""Pure session/run transitions. No I/O; sequence numbers assigned by persistence."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from typed_code.domain.clock import Clock, isoformat, utc_now
from typed_code.domain.errors import DomainConflict, DomainValidationError
from typed_code.domain.ids import (
    new_approval_id,
    new_run_id,
    new_session_id,
    new_transcript_item_id,
)
from typed_code.domain.session import ApprovalState, RunState, SessionState
from typed_code.protocol.common import (
    TERMINAL_RUN_STATUSES,
    ApprovalDecision,
    ApprovalStatus,
    EventType,
    ProviderName,
    RunStatus,
    SessionPhase,
)
from typed_code.protocol.errors import StructuredError
from typed_code.protocol.events import (
    ApprovalRequestedData,
    ApprovalResolvedData,
    ContextCompactedData,
    EventData,
    MessageAssistantDeltaData,
    MessageAssistantDoneData,
    MessageUserData,
    RunCancelledData,
    RunCompletedData,
    RunFailedData,
    RunInterruptedData,
    RunStartedData,
    SessionModelChangedData,
    ThinkingDeltaData,
    ThinkingDoneData,
    UsageUpdatedData,
)
from typed_code.protocol.transcript import (
    AssistantMessageItem,
    SystemNoticeItem,
    ThinkingItem,
    UserMessageItem,
)


@dataclass(frozen=True)
class EventDraft:
    """Public event payload before sequence allocation."""

    type: EventType
    data: EventData
    run_id: str | None = None
    timestamp: str | None = None


@dataclass(frozen=True)
class TranscriptDraft:
    item: Any  # TranscriptItem models
    position: int | None = None


@dataclass(frozen=True)
class ModelMessageDraft:
    role: str
    payload_json: str
    run_id: str | None = None


@dataclass
class TransitionResult:
    session: SessionState
    events: list[EventDraft] = field(default_factory=list)
    transcript_items: list[Any] = field(default_factory=list)
    model_messages: list[ModelMessageDraft] = field(default_factory=list)
    approvals: list[ApprovalState] = field(default_factory=list)
    new_run: RunState | None = None
    updated_run: RunState | None = None


def _preview(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def create_session(
    *,
    workspace_path: str,
    provider: ProviderName,
    model: str,
    clock: Clock = utc_now,
    session_id: str | None = None,
) -> TransitionResult:
    path = workspace_path.strip()
    if not path:
        raise DomainValidationError("workspace_path must be non-empty")
    model_id = model.strip()
    if not model_id:
        raise DomainValidationError("model must be non-empty")

    now = isoformat(clock())
    session = SessionState(
        session_id=session_id or new_session_id(),
        workspace_path=path,
        provider=provider,
        model=model_id,
        phase=SessionPhase.IDLE,
        revision=1,
        latest_event_sequence=0,
        created_at=now,
        updated_at=now,
    )
    return TransitionResult(session=session)


def update_session_model(
    session: SessionState,
    *,
    provider: ProviderName,
    model: str,
    clock: Clock = utc_now,
) -> TransitionResult:
    """Change provider/model while idle. Caller must have validated availability."""
    if session.phase is not SessionPhase.IDLE or session.active_run is not None:
        raise DomainConflict("session model can only be changed while idle")
    model_id = model.strip()
    if not model_id:
        raise DomainValidationError("model must be non-empty")

    now = isoformat(clock())
    notice = SystemNoticeItem(
        id=new_transcript_item_id(),
        created_at=now,
        text=f"Model set to {provider.value}/{model_id}",
        kind="model_changed",
    )
    next_session = replace(
        session,
        provider=provider,
        model=model_id,
        revision=session.revision + 1,
        updated_at=now,
        transcript=[*session.transcript, notice],
    )
    return TransitionResult(
        session=next_session,
        events=[
            EventDraft(
                type=EventType.SESSION_MODEL_CHANGED,
                timestamp=now,
                data=SessionModelChangedData(provider=provider, model=model_id),
            )
        ],
        transcript_items=[notice],
    )


def start_turn(
    session: SessionState,
    prompt: str,
    *,
    clock: Clock = utc_now,
    run_id: str | None = None,
) -> TransitionResult:
    text = prompt.strip()
    if not text:
        raise DomainValidationError("prompt must be non-empty")
    if session.phase != SessionPhase.IDLE or session.active_run is not None:
        raise DomainConflict("session already has an active run")

    now = isoformat(clock())
    rid = run_id or new_run_id()
    run = RunState(
        run_id=rid,
        session_id=session.session_id,
        status=RunStatus.RUNNING,
        prompt=text,
        started_at=now,
    )
    user_item = UserMessageItem(
        id=new_transcript_item_id(),
        created_at=now,
        text=text,
    )
    next_session = replace(
        session,
        phase=SessionPhase.RUNNING,
        revision=session.revision + 1,
        updated_at=now,
        active_run=run,
        transcript=[*session.transcript, user_item],
    )
    events = [
        EventDraft(
            type=EventType.RUN_STARTED,
            run_id=rid,
            timestamp=now,
            data=RunStartedData(run_id=rid, prompt_preview=_preview(text)),
        ),
        EventDraft(
            type=EventType.MESSAGE_USER,
            run_id=rid,
            timestamp=now,
            data=MessageUserData(item=user_item),
        ),
    ]
    return TransitionResult(
        session=next_session,
        events=events,
        transcript_items=[user_item],
        model_messages=[
            ModelMessageDraft(
                role="user",
                payload_json='{"text":' + _json_str(text) + "}",
                run_id=rid,
            )
        ],
        new_run=run,
        updated_run=run,
    )


def _json_str(value: str) -> str:
    import json

    return json.dumps(value)


def _require_active_run(session: SessionState) -> RunState:
    if session.active_run is None:
        raise DomainConflict("session has no active run")
    return session.active_run


def _cancel_pending_approvals(
    session: SessionState, *, now: str
) -> list[ApprovalState]:
    cancelled: list[ApprovalState] = []
    for approval in session.pending_approvals:
        if approval.status != ApprovalStatus.PENDING:
            continue
        cancelled.append(
            replace(
                approval,
                status=ApprovalStatus.CANCELLED,
                decision=None,
                resolved_at=now,
            )
        )
    return cancelled


def _terminal_result(
    session: SessionState,
    *,
    status: RunStatus,
    event_type: EventType,
    data: EventData,
    clock: Clock,
    notice: str | None = None,
) -> TransitionResult:
    run = _require_active_run(session)
    if run.status in TERMINAL_RUN_STATUSES:
        raise DomainConflict(f"run is already terminal ({run.status})")

    now = isoformat(clock())
    ended = replace(run, status=status, ended_at=now)
    transcript = list(session.transcript)
    new_items: list[Any] = []
    if notice:
        item = SystemNoticeItem(
            id=new_transcript_item_id(),
            created_at=now,
            text=notice,
            kind=status.value,
        )
        transcript.append(item)
        new_items.append(item)

    cancelled_approvals = _cancel_pending_approvals(session, now=now)
    next_session = replace(
        session,
        phase=SessionPhase.IDLE,
        revision=session.revision + 1,
        updated_at=now,
        active_run=None,
        pending_approvals=[],
        transcript=transcript,
    )
    return TransitionResult(
        session=next_session,
        events=[
            EventDraft(
                type=event_type,
                run_id=run.run_id,
                timestamp=now,
                data=data,
            )
        ],
        transcript_items=new_items,
        approvals=cancelled_approvals,
        updated_run=ended,
    )


def complete_run(session: SessionState, *, clock: Clock = utc_now) -> TransitionResult:
    run = _require_active_run(session)
    return _terminal_result(
        session,
        status=RunStatus.COMPLETED,
        event_type=EventType.RUN_COMPLETED,
        data=RunCompletedData(run_id=run.run_id),
        clock=clock,
    )


def fail_run(
    session: SessionState,
    *,
    error: StructuredError,
    clock: Clock = utc_now,
) -> TransitionResult:
    run = _require_active_run(session)
    if run.status in TERMINAL_RUN_STATUSES:
        raise DomainConflict(f"run is already terminal ({run.status})")
    now = isoformat(clock())
    ended = replace(
        run,
        status=RunStatus.FAILED,
        ended_at=now,
        error_code=error.code.value,
        error_message=error.message,
    )
    cancelled_approvals = _cancel_pending_approvals(session, now=now)
    next_session = replace(
        session,
        phase=SessionPhase.IDLE,
        revision=session.revision + 1,
        updated_at=now,
        active_run=None,
        pending_approvals=[],
    )
    return TransitionResult(
        session=next_session,
        events=[
            EventDraft(
                type=EventType.RUN_FAILED,
                run_id=run.run_id,
                timestamp=now,
                data=RunFailedData(run_id=run.run_id, error=error),
            )
        ],
        approvals=cancelled_approvals,
        updated_run=ended,
    )


def cancel_run(session: SessionState, *, clock: Clock = utc_now) -> TransitionResult:
    run = _require_active_run(session)
    if run.status in TERMINAL_RUN_STATUSES:
        # Idempotent: already terminal — caller should treat as no-op at API layer.
        raise DomainConflict(f"run is already terminal ({run.status})")
    return _terminal_result(
        session,
        status=RunStatus.CANCELLED,
        event_type=EventType.RUN_CANCELLED,
        data=RunCancelledData(run_id=run.run_id),
        clock=clock,
        notice="Run cancelled",
    )


def interrupt_run(session: SessionState, *, clock: Clock = utc_now) -> TransitionResult:
    run = _require_active_run(session)
    if run.status in TERMINAL_RUN_STATUSES:
        raise DomainConflict(f"run is already terminal ({run.status})")
    return _terminal_result(
        session,
        status=RunStatus.INTERRUPTED,
        event_type=EventType.RUN_INTERRUPTED,
        data=RunInterruptedData(run_id=run.run_id),
        clock=clock,
        notice="Run interrupted by service restart",
    )


def request_approval(
    session: SessionState,
    *,
    tool_call_id: str,
    tool_name: str,
    summary: str,
    request_json: str,
    clock: Clock = utc_now,
    approval_id: str | None = None,
) -> TransitionResult:
    run = _require_active_run(session)
    if run.status in TERMINAL_RUN_STATUSES:
        raise DomainConflict("cannot request approval on a terminal run")

    now = isoformat(clock())
    approval = ApprovalState(
        approval_id=approval_id or new_approval_id(),
        session_id=session.session_id,
        run_id=run.run_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        request_json=request_json,
        status=ApprovalStatus.PENDING,
        summary=summary,
        created_at=now,
    )
    updated_run = replace(run, status=RunStatus.AWAITING_APPROVAL)
    from typed_code.protocol.approvals import ApprovalSummary

    summary_model = ApprovalSummary(
        approval_id=approval.approval_id,
        run_id=approval.run_id,
        tool_name=approval.tool_name,
        summary=approval.summary,
        status=approval.status,
        created_at=approval.created_at,
    )
    next_session = replace(
        session,
        phase=SessionPhase.AWAITING_APPROVAL,
        revision=session.revision + 1,
        updated_at=now,
        active_run=updated_run,
        pending_approvals=[*session.pending_approvals, approval],
    )
    return TransitionResult(
        session=next_session,
        events=[
            EventDraft(
                type=EventType.APPROVAL_REQUESTED,
                run_id=run.run_id,
                timestamp=now,
                data=ApprovalRequestedData(approval=summary_model),
            )
        ],
        approvals=[approval],
        updated_run=updated_run,
    )


def record_assistant_delta(
    session: SessionState,
    *,
    message_id: str,
    delta: str,
    clock: Clock = utc_now,
) -> TransitionResult:
    """Publish one durable assistant stream fragment without changing snapshot content."""
    run = _require_active_run(session)
    if not delta:
        return TransitionResult(session=session)
    now = isoformat(clock())
    return TransitionResult(
        session=replace(session, updated_at=now),
        events=[
            EventDraft(
                type=EventType.MESSAGE_ASSISTANT_DELTA,
                run_id=run.run_id,
                timestamp=now,
                data=MessageAssistantDeltaData(message_id=message_id, delta=delta),
            )
        ],
    )


def record_thinking_delta(
    session: SessionState,
    *,
    thinking_id: str,
    delta: str,
    clock: Clock = utc_now,
) -> TransitionResult:
    """Publish one durable reasoning stream fragment without changing snapshot content."""
    run = _require_active_run(session)
    if not delta:
        return TransitionResult(session=session)
    now = isoformat(clock())
    return TransitionResult(
        session=replace(session, updated_at=now),
        events=[
            EventDraft(
                type=EventType.THINKING_DELTA,
                run_id=run.run_id,
                timestamp=now,
                data=ThinkingDeltaData(thinking_id=thinking_id, delta=delta),
            )
        ],
    )


def finish_thinking(
    session: SessionState,
    *,
    thinking_id: str,
    text: str,
    clock: Clock = utc_now,
) -> TransitionResult:
    """Commit completed reasoning so snapshots and replay converge."""
    run = _require_active_run(session)
    now = isoformat(clock())
    item = ThinkingItem(id=thinking_id, created_at=now, text=text)
    return TransitionResult(
        session=replace(
            session,
            revision=session.revision + 1,
            updated_at=now,
            transcript=[*session.transcript, item],
        ),
        events=[
            EventDraft(
                type=EventType.THINKING_DONE,
                run_id=run.run_id,
                timestamp=now,
                data=ThinkingDoneData(thinking_id=thinking_id, text=text),
            )
        ],
        transcript_items=[item],
    )


def finish_assistant_turn(
    session: SessionState,
    *,
    assistant_text: str,
    model_message_payloads: list[ModelMessageDraft],
    usage: dict[str, int | None] | None = None,
    clock: Clock = utc_now,
    message_id: str | None = None,
) -> TransitionResult:
    """Record assistant output, optional usage, and complete the active run."""
    run = _require_active_run(session)
    if run.status in TERMINAL_RUN_STATUSES:
        raise DomainConflict(f"run is already terminal ({run.status})")

    now = isoformat(clock())
    mid = message_id or new_transcript_item_id()
    item = AssistantMessageItem(id=mid, created_at=now, text=assistant_text)
    ended = replace(run, status=RunStatus.COMPLETED, ended_at=now)
    next_session = replace(
        session,
        phase=SessionPhase.IDLE,
        revision=session.revision + 1,
        updated_at=now,
        active_run=None,
        pending_approvals=[],
        transcript=[*session.transcript, item],
    )
    events: list[EventDraft] = [
        EventDraft(
            type=EventType.MESSAGE_ASSISTANT_DONE,
            run_id=run.run_id,
            timestamp=now,
            data=MessageAssistantDoneData(message_id=mid, text=assistant_text),
        ),
    ]
    if usage:
        events.append(
            EventDraft(
                type=EventType.USAGE_UPDATED,
                run_id=run.run_id,
                timestamp=now,
                data=UsageUpdatedData(
                    input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                    total_tokens=usage.get("total_tokens"),
                ),
            )
        )
    events.append(
        EventDraft(
            type=EventType.RUN_COMPLETED,
            run_id=run.run_id,
            timestamp=now,
            data=RunCompletedData(run_id=run.run_id),
        )
    )
    return TransitionResult(
        session=next_session,
        events=events,
        transcript_items=[item],
        model_messages=list(model_message_payloads),
        updated_run=ended,
    )


def record_compaction(
    session: SessionState,
    *,
    reason: str,
    removed_item_count: int,
    clock: Clock = utc_now,
) -> TransitionResult:
    now = isoformat(clock())
    next_session = replace(
        session,
        revision=session.revision + 1,
        updated_at=now,
    )
    return TransitionResult(
        session=next_session,
        events=[
            EventDraft(
                type=EventType.CONTEXT_COMPACTED,
                run_id=session.active_run.run_id if session.active_run else None,
                timestamp=now,
                data=ContextCompactedData(
                    reason=reason,
                    removed_item_count=removed_item_count,
                ),
            )
        ],
    )


def resolve_approval(
    session: SessionState,
    *,
    approval_id: str,
    decision: ApprovalDecision,
    clock: Clock = utc_now,
) -> TransitionResult:
    run = _require_active_run(session)
    pending = next((a for a in session.pending_approvals if a.approval_id == approval_id), None)
    if pending is None or pending.status != ApprovalStatus.PENDING:
        raise DomainConflict("approval is not pending for this session")

    now = isoformat(clock())
    status = (
        ApprovalStatus.APPROVED
        if decision == ApprovalDecision.APPROVE
        else ApprovalStatus.REJECTED
    )
    resolved = replace(
        pending,
        status=status,
        decision=decision.value,
        resolved_at=now,
    )
    remaining = [a for a in session.pending_approvals if a.approval_id != approval_id]
    phase = SessionPhase.AWAITING_APPROVAL if remaining else SessionPhase.RUNNING
    run_status = RunStatus.AWAITING_APPROVAL if remaining else RunStatus.RUNNING
    updated_run = replace(run, status=run_status)
    next_session = replace(
        session,
        phase=phase,
        revision=session.revision + 1,
        updated_at=now,
        active_run=updated_run,
        pending_approvals=remaining,
    )
    return TransitionResult(
        session=next_session,
        events=[
            EventDraft(
                type=EventType.APPROVAL_RESOLVED,
                run_id=run.run_id,
                timestamp=now,
                data=ApprovalResolvedData(approval_id=approval_id, decision=decision),
            )
        ],
        approvals=[resolved],
        updated_run=updated_run,
    )


