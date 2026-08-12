"""Public protocol models for HTTP/SSE contracts.

Pydantic AI, provider SDK, and SQLite row types MUST NOT appear here.
"""

from __future__ import annotations

from typed_code.protocol.approvals import ApprovalDecisionRequest, ApprovalSummary
from typed_code.protocol.common import (
    PROTOCOL_VERSION,
    TERMINAL_RUN_STATUSES,
    ApprovalDecision,
    ApprovalStatus,
    EventType,
    ProtocolVersion,
    ProviderAvailability,
    ProviderName,
    RunStatus,
    SessionPhase,
    ToolCallStatus,
    TranscriptItemType,
)
from typed_code.protocol.errors import ErrorCode, ErrorResponse, StructuredError
from typed_code.protocol.events import EventData, EventEnvelope
from typed_code.protocol.health import (
    ActiveWorkSummary,
    BashHealth,
    HealthResponse,
    ServiceHealth,
    ServiceStopRequest,
    ServiceStopResponse,
)
from typed_code.protocol.models import ModelCapabilities, ModelInfo, ModelListResponse
from typed_code.protocol.requests import AbortRequest, CreateTurnRequest
from typed_code.protocol.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    CreateTurnResponse,
    RunSummary,
    SessionListResponse,
    SessionSnapshot,
    SessionSummary,
)
from typed_code.protocol.transcript import TranscriptItem

__all__ = [
    "PROTOCOL_VERSION",
    "TERMINAL_RUN_STATUSES",
    "AbortRequest",
    "ApprovalDecision",
    "ApprovalDecisionRequest",
    "ApprovalStatus",
    "ActiveWorkSummary",
    "BashHealth",
    "ApprovalSummary",
    "CreateSessionRequest",
    "CreateSessionResponse",
    "CreateTurnRequest",
    "CreateTurnResponse",
    "ErrorCode",
    "ErrorResponse",
    "EventData",
    "EventEnvelope",
    "EventType",
    "HealthResponse",
    "ModelCapabilities",
    "ModelInfo",
    "ModelListResponse",
    "ProtocolVersion",
    "ProviderAvailability",
    "ProviderName",
    "RunStatus",
    "RunSummary",
    "SessionListResponse",
    "SessionPhase",
    "ServiceHealth",
    "ServiceStopRequest",
    "ServiceStopResponse",
    "SessionSnapshot",
    "SessionSummary",
    "StructuredError",
    "ToolCallStatus",
    "TranscriptItem",
    "TranscriptItemType",
]
