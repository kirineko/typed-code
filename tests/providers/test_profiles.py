"""Provider capability profiles."""

from __future__ import annotations

from typed_code.protocol.common import ProviderName
from typed_code.providers.profiles import (
    DEEPSEEK_CONTEXT_TOKEN_BUDGET,
    DEEPSEEK_MODEL_ID,
    DEEPSEEK_PROFILE,
    DEFAULT_CONTEXT_TOKEN_BUDGET,
    OPENAI_FAMILY_CONTEXT_TOKEN_BUDGET,
    cliproxy_profile,
    profile_for,
    resolve_context_token_budget,
)


def test_deepseek_profile_stateless_no_previous_response() -> None:
    p = DEEPSEEK_PROFILE
    assert p.provider is ProviderName.DEEPSEEK
    assert p.model_id == DEEPSEEK_MODEL_ID
    assert p.history_strategy == "stateless_full_replay"
    assert p.supports_previous_response_id is False
    assert p.image_input is False
    assert p.tools is True
    assert p.parallel_tool_calls is True
    assert p.context_token_budget == DEEPSEEK_CONTEXT_TOKEN_BUDGET


def test_cliproxy_profile_per_model() -> None:
    p = cliproxy_profile("gpt-5.6-sol")
    assert p.provider is ProviderName.CLIPROXY
    assert p.model_id == "gpt-5.6-sol"
    assert p.supports_previous_response_id is False
    assert p.context_token_budget == OPENAI_FAMILY_CONTEXT_TOKEN_BUDGET
    caps = p.to_public_capabilities()
    assert caps.text_input is True
    assert caps.image_input is False


def test_cliproxy_unknown_model_budget() -> None:
    p = cliproxy_profile("local-llama-custom")
    assert p.context_token_budget == DEFAULT_CONTEXT_TOKEN_BUDGET


def test_resolve_context_token_budget_matrix() -> None:
    assert (
        resolve_context_token_budget(ProviderName.DEEPSEEK, DEEPSEEK_MODEL_ID)
        == DEEPSEEK_CONTEXT_TOKEN_BUDGET
    )
    assert (
        resolve_context_token_budget(ProviderName.CLIPROXY, "gpt-5.6-sol")
        == OPENAI_FAMILY_CONTEXT_TOKEN_BUDGET
    )
    assert (
        resolve_context_token_budget(ProviderName.CLIPROXY, "gpt-5.4")
        == OPENAI_FAMILY_CONTEXT_TOKEN_BUDGET
    )
    assert (
        resolve_context_token_budget(ProviderName.CLIPROXY, "codex-auto-review")
        == DEFAULT_CONTEXT_TOKEN_BUDGET
    )


def test_profile_for_dispatch() -> None:
    assert profile_for(ProviderName.DEEPSEEK, DEEPSEEK_MODEL_ID) is DEEPSEEK_PROFILE
    assert profile_for(ProviderName.CLIPROXY, "x").model_id == "x"
    assert (
        profile_for(ProviderName.CLIPROXY, "gpt-5.5").context_token_budget
        == OPENAI_FAMILY_CONTEXT_TOKEN_BUDGET
    )
