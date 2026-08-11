"""Inbound command models for turns and abort."""

from __future__ import annotations

from pydantic import field_validator

from typed_code.protocol.common import ProviderName, StrictCommandModel


class CreateTurnRequest(StrictCommandModel):
    prompt: str

    @field_validator("prompt")
    @classmethod
    def _non_empty_prompt(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("prompt must be non-empty")
        return stripped


class AbortRequest(StrictCommandModel):
    """Optional body for abort; empty object is valid."""


class UpdateSessionModelRequest(StrictCommandModel):
    provider: ProviderName
    model: str

    @field_validator("model")
    @classmethod
    def _non_empty_model(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("model must be non-empty")
        return stripped
