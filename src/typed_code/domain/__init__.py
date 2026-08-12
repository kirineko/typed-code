"""Session and run domain state machines (no I/O)."""

from __future__ import annotations

from typed_code.domain.errors import (
    DomainConflict,
    DomainError,
    DomainNotFound,
    DomainValidationError,
)
from typed_code.domain.session import (
    ApprovalState,
    ContextUsageCheckpoint,
    RunState,
    SessionState,
)
from typed_code.domain.tool_activity import finish_tool, record_tool_started
from typed_code.domain.transitions import (
    TransitionResult,
    cancel_run,
    complete_run,
    create_session,
    fail_run,
    finish_assistant_turn,
    finish_thinking,
    interrupt_run,
    record_assistant_delta,
    record_compaction,
    record_thinking_delta,
    request_approval,
    resolve_approval,
    start_turn,
    update_session_model,
)

__all__ = [
    "ApprovalState",
    "ContextUsageCheckpoint",
    "DomainConflict",
    "DomainError",
    "DomainNotFound",
    "DomainValidationError",
    "RunState",
    "SessionState",
    "TransitionResult",
    "cancel_run",
    "complete_run",
    "create_session",
    "fail_run",
    "finish_assistant_turn",
    "finish_thinking",
    "finish_tool",
    "interrupt_run",
    "record_assistant_delta",
    "record_compaction",
    "record_thinking_delta",
    "record_tool_started",
    "request_approval",
    "resolve_approval",
    "start_turn",
    "update_session_model",
]
