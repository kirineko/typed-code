"""In-memory session and run aggregates used by pure transitions."""

from __future__ import annotations

from dataclasses import dataclass, field

from typed_code.protocol.common import (
    ApprovalStatus,
    ProviderName,
    RunStatus,
    SessionPhase,
)
from typed_code.protocol.transcript import TranscriptItem


@dataclass
class RunState:
    run_id: str
    session_id: str
    status: RunStatus
    prompt: str
    started_at: str
    ended_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class ApprovalState:
    approval_id: str
    session_id: str
    run_id: str
    tool_call_id: str
    tool_name: str
    request_json: str
    status: ApprovalStatus
    summary: str
    created_at: str
    decision: str | None = None
    resolved_at: str | None = None


@dataclass
class ContextUsageCheckpoint:
    """Provider usage anchor for hybrid context token estimates.

    ``message_count`` is the number of PAI model_messages rows covered by
    ``tokens`` (deepy ``last_usage_record_count`` analogue).
    """

    tokens: int
    message_count: int


@dataclass
class SessionState:
    session_id: str
    workspace_path: str
    provider: ProviderName
    model: str
    phase: SessionPhase
    revision: int
    latest_event_sequence: int
    created_at: str
    updated_at: str
    active_run: RunState | None = None
    pending_approvals: list[ApprovalState] = field(default_factory=list)
    transcript: list[TranscriptItem] = field(default_factory=list)
    context_usage: ContextUsageCheckpoint | None = None
