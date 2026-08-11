"""Shared protocol primitives."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

PROTOCOL_VERSION: Literal[1] = 1
ProtocolVersion = Literal[1]


class ProtocolModel(BaseModel):
    """Base for outbound/public models (ignore unknown on decode for forward-compat)."""

    model_config = ConfigDict(extra="ignore")


class StrictCommandModel(BaseModel):
    """Base for inbound client commands (reject unknown fields)."""

    model_config = ConfigDict(extra="forbid")


class SessionPhase(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"


class RunStatus(StrEnum):
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


TERMINAL_RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    }
)


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"


class ProviderName(StrEnum):
    DEEPSEEK = "deepseek"
    CLIPROXY = "cliproxy"


class ProviderAvailability(StrEnum):
    AVAILABLE = "available"
    MISSING_CREDENTIALS = "missing_credentials"


class TranscriptItemType(StrEnum):
    USER_MESSAGE = "user_message"
    ASSISTANT_MESSAGE = "assistant_message"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    SYSTEM_NOTICE = "system_notice"


class ToolCallStatus(StrEnum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"


class EventType(StrEnum):
    SESSION_SNAPSHOT = "session.snapshot"
    SESSION_MODEL_CHANGED = "session.model_changed"
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
    RUN_INTERRUPTED = "run.interrupted"
    MESSAGE_USER = "message.user"
    MESSAGE_ASSISTANT_DELTA = "message.assistant.delta"
    MESSAGE_ASSISTANT_DONE = "message.assistant.done"
    THINKING_DELTA = "thinking.delta"
    THINKING_DONE = "thinking.done"
    TOOL_STARTED = "tool.started"
    TOOL_UPDATED = "tool.updated"
    TOOL_COMPLETED = "tool.completed"
    TOOL_FAILED = "tool.failed"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_RESOLVED = "approval.resolved"
    USAGE_UPDATED = "usage.updated"
    CONTEXT_COMPACTED = "context.compacted"
    ERROR = "error"
    REPLAY_RESET = "replay.reset"
