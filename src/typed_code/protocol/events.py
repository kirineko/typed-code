"""SSE/public event envelopes and typed payloads."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from typed_code.protocol.approvals import ApprovalSummary
from typed_code.protocol.common import (
    PROTOCOL_VERSION,
    ApprovalDecision,
    EventType,
    ProtocolModel,
    ProtocolVersion,
    ProviderName,
    ToolCallStatus,
)
from typed_code.protocol.errors import StructuredError
from typed_code.protocol.sessions import SessionSnapshot
from typed_code.protocol.transcript import TranscriptItem


class EventDataBase(ProtocolModel):
    pass


class SessionSnapshotData(EventDataBase):
    type: Literal[EventType.SESSION_SNAPSHOT] = EventType.SESSION_SNAPSHOT
    snapshot: SessionSnapshot


class SessionModelChangedData(EventDataBase):
    type: Literal[EventType.SESSION_MODEL_CHANGED] = EventType.SESSION_MODEL_CHANGED
    provider: ProviderName
    model: str


class RunStartedData(EventDataBase):
    type: Literal[EventType.RUN_STARTED] = EventType.RUN_STARTED
    run_id: str
    prompt_preview: str


class RunCompletedData(EventDataBase):
    type: Literal[EventType.RUN_COMPLETED] = EventType.RUN_COMPLETED
    run_id: str


class RunFailedData(EventDataBase):
    type: Literal[EventType.RUN_FAILED] = EventType.RUN_FAILED
    run_id: str
    error: StructuredError


class RunCancelledData(EventDataBase):
    type: Literal[EventType.RUN_CANCELLED] = EventType.RUN_CANCELLED
    run_id: str


class RunInterruptedData(EventDataBase):
    type: Literal[EventType.RUN_INTERRUPTED] = EventType.RUN_INTERRUPTED
    run_id: str


class MessageUserData(EventDataBase):
    type: Literal[EventType.MESSAGE_USER] = EventType.MESSAGE_USER
    item: TranscriptItem


class MessageAssistantDeltaData(EventDataBase):
    type: Literal[EventType.MESSAGE_ASSISTANT_DELTA] = EventType.MESSAGE_ASSISTANT_DELTA
    message_id: str
    delta: str


class MessageAssistantDoneData(EventDataBase):
    type: Literal[EventType.MESSAGE_ASSISTANT_DONE] = EventType.MESSAGE_ASSISTANT_DONE
    message_id: str
    text: str


class ThinkingDeltaData(EventDataBase):
    type: Literal[EventType.THINKING_DELTA] = EventType.THINKING_DELTA
    thinking_id: str
    delta: str


class ThinkingDoneData(EventDataBase):
    type: Literal[EventType.THINKING_DONE] = EventType.THINKING_DONE
    thinking_id: str
    text: str


class ToolStartedData(EventDataBase):
    type: Literal[EventType.TOOL_STARTED] = EventType.TOOL_STARTED
    tool_call_id: str
    tool_name: str
    summary: str
    status: ToolCallStatus = ToolCallStatus.STARTED


class ToolUpdatedData(EventDataBase):
    type: Literal[EventType.TOOL_UPDATED] = EventType.TOOL_UPDATED
    tool_call_id: str
    summary: str
    status: ToolCallStatus


class ToolCompletedData(EventDataBase):
    type: Literal[EventType.TOOL_COMPLETED] = EventType.TOOL_COMPLETED
    tool_call_id: str
    summary: str
    ok: bool = True


class ToolFailedData(EventDataBase):
    type: Literal[EventType.TOOL_FAILED] = EventType.TOOL_FAILED
    tool_call_id: str
    summary: str


class ApprovalRequestedData(EventDataBase):
    type: Literal[EventType.APPROVAL_REQUESTED] = EventType.APPROVAL_REQUESTED
    approval: ApprovalSummary


class ApprovalResolvedData(EventDataBase):
    type: Literal[EventType.APPROVAL_RESOLVED] = EventType.APPROVAL_RESOLVED
    approval_id: str
    decision: ApprovalDecision


class UsageUpdatedData(EventDataBase):
    type: Literal[EventType.USAGE_UPDATED] = EventType.USAGE_UPDATED
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    details: dict[str, Any] | None = None


class ContextCompactedData(EventDataBase):
    type: Literal[EventType.CONTEXT_COMPACTED] = EventType.CONTEXT_COMPACTED
    reason: str
    removed_item_count: int = 0


class ErrorEventData(EventDataBase):
    type: Literal[EventType.ERROR] = EventType.ERROR
    error: StructuredError


class ReplayResetData(EventDataBase):
    type: Literal[EventType.REPLAY_RESET] = EventType.REPLAY_RESET
    reason: str = "event_window_expired"
    snapshot: SessionSnapshot


EventData = Annotated[
    SessionSnapshotData
    | SessionModelChangedData
    | RunStartedData
    | RunCompletedData
    | RunFailedData
    | RunCancelledData
    | RunInterruptedData
    | MessageUserData
    | MessageAssistantDeltaData
    | MessageAssistantDoneData
    | ThinkingDeltaData
    | ThinkingDoneData
    | ToolStartedData
    | ToolUpdatedData
    | ToolCompletedData
    | ToolFailedData
    | ApprovalRequestedData
    | ApprovalResolvedData
    | UsageUpdatedData
    | ContextCompactedData
    | ErrorEventData
    | ReplayResetData,
    Field(discriminator="type"),
]


class EventEnvelope(ProtocolModel):
    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    sequence: int = Field(ge=1)
    timestamp: str
    session_id: str
    run_id: str | None = None
    type: EventType
    data: EventData
