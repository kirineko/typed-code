"""Approval summaries and client decision commands."""

from __future__ import annotations

from typed_code.protocol.common import (
    ApprovalDecision,
    ApprovalStatus,
    ProtocolModel,
    StrictCommandModel,
)


class ApprovalSummary(ProtocolModel):
    approval_id: str
    run_id: str
    tool_name: str
    summary: str
    status: ApprovalStatus
    created_at: str


class ApprovalDecisionRequest(StrictCommandModel):
    """Client decision for a pending server-issued approval."""

    decision: ApprovalDecision
