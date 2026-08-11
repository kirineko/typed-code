"""Derive effective run settings from profiles; reject unsupported modalities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from typed_code.domain.errors import DomainValidationError
from typed_code.protocol.common import ProviderName
from typed_code.protocol.errors import ErrorCode
from typed_code.providers.profiles import ProviderProfile


@dataclass(frozen=True)
class RunSettingRequest:
    """Optional client/runtime-requested knobs (none are secrets)."""

    temperature: float | None = None
    max_output_tokens: int | None = None
    reasoning_level: str | None = None
    tool_choice: str | None = None
    parallel_tool_calls: bool | None = None
    # Explicit modality flags for validation (MVP: reject if true and unsupported)
    image_input: bool = False
    file_input: bool = False
    # Opaque passthrough keys to evaluate omit/reject
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class EffectiveRunSettings:
    provider: ProviderName
    model_id: str
    temperature: float | None
    max_output_tokens: int | None
    reasoning_level: str | None
    tool_choice: str | None
    parallel_tool_calls: bool | None
    history_strategy: str
    send_previous_response_id: bool
    omitted: tuple[str, ...]
    profile: ProviderProfile


class ModelSelectionError(DomainValidationError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = ErrorCode.MODEL_SELECTION_ERROR


def normalize_settings(
    profile: ProviderProfile,
    *,
    model_id: str,
    requested: RunSettingRequest | None = None,
) -> EffectiveRunSettings:
    req = requested or RunSettingRequest()
    omitted: list[str] = []

    if req.image_input and not profile.image_input:
        raise DomainValidationError(
            "image input is not supported by the selected provider profile"
        )
    if req.file_input and not profile.file_input:
        raise DomainValidationError(
            "file input is not supported by the selected provider profile"
        )

    extra = dict(req.extra or {})
    for key in list(extra):
        if key in profile.reject_settings:
            raise DomainValidationError(
                f"setting {key!r} is not supported by the selected provider profile"
            )
        if key in profile.omit_settings:
            extra.pop(key, None)
            omitted.append(key)

    # Always omit previous_response_id for MVP profiles
    if not profile.supports_previous_response_id:
        for key in ("previous_response_id", "openai_previous_response_id"):
            if key not in omitted:
                omitted.append(key)

    reasoning = (
        req.reasoning_level
        if req.reasoning_level is not None
        else profile.default_reasoning_level
    )
    if reasoning is not None:
        if profile.reasoning_levels and reasoning not in profile.reasoning_levels:
            raise DomainValidationError(
                f"reasoning level {reasoning!r} is not supported by this profile"
            )
        if not profile.reasoning_levels:
            omitted.append("reasoning_level")
            reasoning = None

    tool_choice = req.tool_choice
    if tool_choice is not None and tool_choice not in profile.tool_choice_modes:
        raise DomainValidationError(
            f"tool_choice {tool_choice!r} is not supported by this profile"
        )

    parallel = req.parallel_tool_calls
    if parallel is False and profile.parallel_tool_calls:
        # DeepSeek may force parallel; omit disable attempts
        omitted.append("parallel_tool_calls")
        parallel = True

    max_out = req.max_output_tokens
    if max_out is None:
        max_out = profile.max_output_tokens
    elif profile.max_output_tokens is not None:
        max_out = min(max_out, profile.max_output_tokens)

    return EffectiveRunSettings(
        provider=profile.provider,
        model_id=model_id,
        temperature=req.temperature,
        max_output_tokens=max_out,
        reasoning_level=reasoning,
        tool_choice=tool_choice,
        parallel_tool_calls=parallel if parallel is not None else profile.parallel_tool_calls,
        history_strategy=profile.history_strategy,
        send_previous_response_id=False,
        omitted=tuple(dict.fromkeys(omitted)),
        profile=profile,
    )
