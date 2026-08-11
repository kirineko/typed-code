"""Map between domain/protocol models and DB rows."""

from __future__ import annotations

import json
from typing import Any

from typed_code.domain.session import ApprovalState, RunState, SessionState
from typed_code.protocol.approvals import ApprovalSummary
from typed_code.protocol.common import (
    ApprovalStatus,
    EventType,
    ProviderName,
    RunStatus,
    SessionPhase,
)
from typed_code.protocol.events import EventEnvelope
from typed_code.protocol.sessions import RunSummary, SessionSnapshot, SessionSummary
from typed_code.protocol.transcript import (
    AssistantMessageItem,
    SystemNoticeItem,
    ThinkingItem,
    ToolCallItem,
    ToolResultItem,
    TranscriptItem,
    UserMessageItem,
)


def run_to_summary(run: RunState) -> RunSummary:
    preview = " ".join(run.prompt.split())
    if len(preview) > 120:
        preview = preview[:119] + "…"
    return RunSummary(
        run_id=run.run_id,
        status=run.status,
        prompt_preview=preview,
        started_at=run.started_at,
        ended_at=run.ended_at,
        error_code=run.error_code,
        error_message=run.error_message,
    )


def approval_to_summary(approval: ApprovalState) -> ApprovalSummary:
    return ApprovalSummary(
        approval_id=approval.approval_id,
        run_id=approval.run_id,
        tool_name=approval.tool_name,
        summary=approval.summary,
        status=approval.status,
        created_at=approval.created_at,
    )


def session_to_summary(session: SessionState) -> SessionSummary:
    return SessionSummary(
        session_id=session.session_id,
        revision=session.revision,
        phase=session.phase,
        workspace_path=session.workspace_path,
        provider=session.provider,
        model=session.model,
        created_at=session.created_at,
        updated_at=session.updated_at,
        active_run_id=session.active_run.run_id if session.active_run else None,
    )


def session_to_snapshot(session: SessionState) -> SessionSnapshot:
    return SessionSnapshot(
        session_id=session.session_id,
        revision=session.revision,
        phase=session.phase,
        workspace_path=session.workspace_path,
        provider=session.provider,
        model=session.model,
        active_run=run_to_summary(session.active_run) if session.active_run else None,
        pending_approvals=[
            approval_to_summary(a)
            for a in session.pending_approvals
            if a.status == ApprovalStatus.PENDING
        ],
        transcript=list(session.transcript),
        created_at=session.created_at,
        updated_at=session.updated_at,
        latest_event_sequence=session.latest_event_sequence,
    )


def parse_transcript_item(payload_json: str) -> TranscriptItem:
    data = json.loads(payload_json)
    item_type = data.get("type")
    if item_type == "user_message":
        return UserMessageItem.model_validate(data)
    if item_type == "assistant_message":
        return AssistantMessageItem.model_validate(data)
    if item_type == "thinking":
        return ThinkingItem.model_validate(data)
    if item_type == "tool_call":
        return ToolCallItem.model_validate(data)
    if item_type == "tool_result":
        return ToolResultItem.model_validate(data)
    if item_type == "system_notice":
        return SystemNoticeItem.model_validate(data)
    raise ValueError(f"unknown transcript item type: {item_type!r}")


def transcript_item_to_json(item: Any) -> str:
    return item.model_dump_json()


def event_data_to_json(data: Any) -> str:
    return data.model_dump_json()


def parse_event_envelope(
    *,
    session_id: str,
    sequence: int,
    run_id: str | None,
    type_value: str,
    data_json: str,
    created_at: str,
) -> EventEnvelope:
    payload = json.loads(data_json)
    # Ensure discriminator present
    if "type" not in payload:
        payload["type"] = type_value
    return EventEnvelope.model_validate(
        {
            "sequence": sequence,
            "timestamp": created_at,
            "session_id": session_id,
            "run_id": run_id,
            "type": type_value,
            "data": payload,
        }
    )


def row_run(row: Any) -> RunState:
    return RunState(
        run_id=row["id"],
        session_id=row["session_id"],
        status=RunStatus(row["status"]),
        prompt=row["prompt"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        error_code=row["error_code"],
        error_message=row["error_message"],
    )


def row_approval(row: Any) -> ApprovalState:
    return ApprovalState(
        approval_id=row["id"],
        session_id=row["session_id"],
        run_id=row["run_id"],
        tool_call_id=row["tool_call_id"],
        tool_name=row["tool_name"],
        request_json=row["request_json"],
        status=ApprovalStatus(row["status"]),
        summary=row["summary"],
        created_at=row["created_at"],
        decision=row["decision"],
        resolved_at=row["resolved_at"],
    )


def row_session_core(row: Any) -> dict[str, Any]:
    keys = set(row.keys()) if hasattr(row, "keys") else set()
    last_usage_tokens = None
    last_usage_message_count = None
    if "last_usage_tokens" in keys:
        raw = row["last_usage_tokens"]
        last_usage_tokens = int(raw) if raw is not None else None
    if "last_usage_message_count" in keys:
        raw = row["last_usage_message_count"]
        last_usage_message_count = int(raw) if raw is not None else None
    return {
        "session_id": row["id"],
        "workspace_path": row["workspace_path"],
        "provider": ProviderName(row["provider"]),
        "model": row["model"],
        "phase": SessionPhase(row["phase"]),
        "revision": int(row["revision"]),
        "latest_event_sequence": int(row["latest_event_sequence"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "active_run_id": row["active_run_id"],
        "last_usage_tokens": last_usage_tokens,
        "last_usage_message_count": last_usage_message_count,
    }


def event_type_value(event_type: EventType | str) -> str:
    return event_type.value if isinstance(event_type, EventType) else str(event_type)
