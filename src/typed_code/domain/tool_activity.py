"""Domain transitions for public tool lifecycle activity."""

from __future__ import annotations

from dataclasses import replace

from typed_code.domain.clock import Clock, isoformat, utc_now
from typed_code.domain.session import SessionState
from typed_code.domain.transitions import EventDraft, TransitionResult, _require_active_run
from typed_code.protocol.common import EventType, ToolCallStatus
from typed_code.protocol.events import ToolCompletedData, ToolFailedData, ToolStartedData
from typed_code.protocol.transcript import ToolCallItem, ToolResultItem


def record_tool_started(
    session: SessionState,
    *,
    tool_call_id: str,
    tool_name: str,
    summary: str,
    clock: Clock = utc_now,
) -> TransitionResult:
    """Publish a live tool start without changing the snapshot transcript."""
    run = _require_active_run(session)
    now = isoformat(clock())
    return TransitionResult(
        session=replace(session, updated_at=now),
        events=[
            EventDraft(
                type=EventType.TOOL_STARTED,
                run_id=run.run_id,
                timestamp=now,
                data=ToolStartedData(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    summary=summary,
                    status=ToolCallStatus.STARTED,
                ),
            )
        ],
    )


def finish_tool(
    session: SessionState,
    *,
    tool_call_id: str,
    tool_name: str,
    summary: str,
    ok: bool,
    call_summary: str | None = None,
    clock: Clock = utc_now,
) -> TransitionResult:
    """Commit a terminal tool presentation so snapshots and replay converge."""
    run = _require_active_run(session)
    now = isoformat(clock())
    status = ToolCallStatus.COMPLETED if ok else ToolCallStatus.FAILED
    call_item = ToolCallItem(
        id=tool_call_id,
        created_at=now,
        tool_name=tool_name,
        summary=call_summary or summary,
        status=status,
    )
    result_item = ToolResultItem(
        id=f"{tool_call_id}:result",
        created_at=now,
        tool_call_id=tool_call_id,
        ok=ok,
        summary=summary,
    )
    event = EventDraft(
        type=EventType.TOOL_COMPLETED if ok else EventType.TOOL_FAILED,
        run_id=run.run_id,
        timestamp=now,
        data=(
            ToolCompletedData(tool_call_id=tool_call_id, summary=summary, ok=True)
            if ok
            else ToolFailedData(tool_call_id=tool_call_id, summary=summary)
        ),
    )
    return TransitionResult(
        session=replace(
            session,
            revision=session.revision + 1,
            updated_at=now,
            transcript=[*session.transcript, call_item, result_item],
        ),
        events=[event],
        transcript_items=[call_item, result_item],
    )
