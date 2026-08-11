"""Session request and snapshot models."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from typed_code.protocol.approvals import ApprovalSummary
from typed_code.protocol.common import (
    PROTOCOL_VERSION,
    ProtocolModel,
    ProtocolVersion,
    ProviderName,
    RunStatus,
    SessionPhase,
    StrictCommandModel,
)
from typed_code.protocol.transcript import TranscriptItem


class CreateSessionRequest(StrictCommandModel):
    workspace_path: str = Field(min_length=1)
    provider: ProviderName | None = None
    model: str | None = None

    @field_validator("workspace_path")
    @classmethod
    def _strip_workspace(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("workspace_path must be non-empty")
        return stripped

    @field_validator("model")
    @classmethod
    def _strip_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RunSummary(ProtocolModel):
    run_id: str
    status: RunStatus
    prompt_preview: str
    started_at: str
    ended_at: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class SessionSummary(ProtocolModel):
    session_id: str
    revision: int
    phase: SessionPhase
    workspace_path: str
    provider: ProviderName
    model: str
    created_at: str
    updated_at: str
    active_run_id: str | None = None


class SessionSnapshot(ProtocolModel):
    protocol_version: ProtocolVersion = PROTOCOL_VERSION
    session_id: str
    revision: int = Field(ge=1)
    phase: SessionPhase
    workspace_path: str
    provider: ProviderName
    model: str
    active_run: RunSummary | None = None
    pending_approvals: list[ApprovalSummary] = Field(default_factory=list)
    transcript: list[TranscriptItem] = Field(default_factory=list)
    created_at: str
    updated_at: str
    latest_event_sequence: int = Field(ge=0, default=0)


class SessionListResponse(ProtocolModel):
    sessions: list[SessionSummary]


class CreateSessionResponse(ProtocolModel):
    snapshot: SessionSnapshot


class CreateTurnResponse(ProtocolModel):
    run_id: str
    revision: int
    phase: SessionPhase
    status: Literal["accepted"] = "accepted"
