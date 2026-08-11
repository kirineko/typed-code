"""Structured public errors."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from typed_code.protocol.common import ProtocolModel


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "validation_error"
    PROTOCOL_VERSION_ERROR = "protocol_version_error"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    MISSING_CREDENTIALS = "missing_credentials"
    MODEL_SELECTION_ERROR = "model_selection_error"
    INTERNAL_ERROR = "internal_error"
    RUN_FAILED = "run_failed"
    CONFIGURATION_ERROR = "configuration_error"


class StructuredError(ProtocolModel):
    """Sanitized error returned to clients (never includes secrets)."""

    code: ErrorCode
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(ProtocolModel):
    error: StructuredError = Field(description="Structured failure payload")
