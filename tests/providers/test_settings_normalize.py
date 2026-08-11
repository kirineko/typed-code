"""Effective settings normalization."""

from __future__ import annotations

import pytest

from typed_code.domain.errors import DomainValidationError
from typed_code.providers.profiles import DEEPSEEK_PROFILE, cliproxy_profile
from typed_code.providers.settings_normalize import RunSettingRequest, normalize_settings


def test_reject_image_input() -> None:
    with pytest.raises(DomainValidationError, match="image"):
        normalize_settings(
            DEEPSEEK_PROFILE,
            model_id="deepseek-v4-flash",
            requested=RunSettingRequest(image_input=True),
        )


def test_omit_previous_response_id() -> None:
    eff = normalize_settings(
        DEEPSEEK_PROFILE,
        model_id="deepseek-v4-flash",
        requested=RunSettingRequest(extra={"previous_response_id": "abc"}),
    )
    assert "previous_response_id" in eff.omitted
    assert eff.send_previous_response_id is False


def test_unsupported_tool_choice_rejected() -> None:
    with pytest.raises(DomainValidationError, match="tool_choice"):
        normalize_settings(
            DEEPSEEK_PROFILE,
            model_id="deepseek-v4-flash",
            requested=RunSettingRequest(tool_choice="required"),
        )


def test_cliproxy_allows_required_tool_choice() -> None:
    eff = normalize_settings(
        cliproxy_profile("m"),
        model_id="m",
        requested=RunSettingRequest(tool_choice="required"),
    )
    assert eff.tool_choice == "required"



def test_supported_models_use_provider_reasoning_defaults() -> None:
    deepseek = normalize_settings(
        DEEPSEEK_PROFILE,
        model_id="deepseek-v4-flash",
    )
    terra = normalize_settings(
        cliproxy_profile("gpt-5.6-terra"),
        model_id="gpt-5.6-terra",
    )
    unknown = normalize_settings(
        cliproxy_profile("plain-model"),
        model_id="plain-model",
    )

    assert deepseek.reasoning_level == "high"
    assert terra.reasoning_level == "medium"
    assert unknown.reasoning_level is None


def test_provider_specific_reasoning_levels_are_validated() -> None:
    deepseek_max = normalize_settings(
        DEEPSEEK_PROFILE,
        model_id="deepseek-v4-flash",
        requested=RunSettingRequest(reasoning_level="max"),
    )
    openai_xhigh = normalize_settings(
        cliproxy_profile("gpt-5.6-terra"),
        model_id="gpt-5.6-terra",
        requested=RunSettingRequest(reasoning_level="xhigh"),
    )
    assert deepseek_max.reasoning_level == "max"
    assert openai_xhigh.reasoning_level == "xhigh"
    with pytest.raises(DomainValidationError, match="not supported"):
        normalize_settings(
            DEEPSEEK_PROFILE,
            model_id="deepseek-v4-flash",
            requested=RunSettingRequest(reasoning_level="medium"),
        )