"""Provider capability profiles for Responses-only execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from typed_code.protocol.common import ProviderName
from typed_code.protocol.models import ModelCapabilities

HistoryStrategy = Literal["stateless_full_replay"]
SettingPolicy = Literal["omit", "reject"]

DEEPSEEK_MODEL_ID = "deepseek-v4-flash"

# Product context budgets (compaction + public model metadata).
DEEPSEEK_CONTEXT_TOKEN_BUDGET = 1_000_000
OPENAI_FAMILY_CONTEXT_TOKEN_BUDGET = 272_000
DEFAULT_CONTEXT_TOKEN_BUDGET = 128_000


def is_openai_family_model_id(model_id: str) -> bool:
    """CLIProxy OpenAI GPT-family ids (product rule for 272k budget)."""
    mid = model_id.strip().lower()
    if not mid:
        return False
    return mid.startswith("gpt-") or mid.startswith("o1") or mid.startswith("o3") or mid.startswith(
        "o4"
    )


def resolve_context_token_budget(provider: ProviderName, model_id: str) -> int:
    """Return context token budget for provider + model selection."""
    if provider is ProviderName.DEEPSEEK:
        return DEEPSEEK_CONTEXT_TOKEN_BUDGET
    if provider is ProviderName.CLIPROXY and is_openai_family_model_id(model_id):
        return OPENAI_FAMILY_CONTEXT_TOKEN_BUDGET
    return DEFAULT_CONTEXT_TOKEN_BUDGET


@dataclass(frozen=True)
class ProviderProfile:
    """Declared capabilities; effective settings are derived from this profile."""

    provider: ProviderName
    model_id: str | None
    history_strategy: HistoryStrategy
    supports_previous_response_id: bool
    text_input: bool
    text_output: bool
    image_input: bool
    file_input: bool
    tools: bool
    parallel_tool_calls: bool
    tool_choice_modes: frozenset[str]
    reasoning_levels: tuple[str, ...]
    context_token_budget: int
    max_output_tokens: int | None
    # Settings keys that must never be forwarded as requested
    omit_settings: frozenset[str]
    reject_settings: frozenset[str]

    def to_public_capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            text_input=self.text_input,
            text_output=self.text_output,
            image_input=self.image_input,
            tools=self.tools,
            parallel_tool_calls=self.parallel_tool_calls,
            reasoning_levels=list(self.reasoning_levels),
        )


DEEPSEEK_PROFILE = ProviderProfile(
    provider=ProviderName.DEEPSEEK,
    model_id=DEEPSEEK_MODEL_ID,
    history_strategy="stateless_full_replay",
    supports_previous_response_id=False,
    text_input=True,
    text_output=True,
    image_input=False,
    file_input=False,
    tools=True,
    parallel_tool_calls=True,
    tool_choice_modes=frozenset({"auto", "none"}),
    reasoning_levels=(),
    context_token_budget=DEEPSEEK_CONTEXT_TOKEN_BUDGET,
    max_output_tokens=8_192,
    omit_settings=frozenset(
        {
            "previous_response_id",
            "openai_previous_response_id",
            "frequency_penalty",
            "presence_penalty",
        }
    ),
    reject_settings=frozenset({"image_input", "file_input"}),
)


def cliproxy_profile(model_id: str) -> ProviderProfile:
    return ProviderProfile(
        provider=ProviderName.CLIPROXY,
        model_id=model_id,
        history_strategy="stateless_full_replay",
        supports_previous_response_id=False,
        text_input=True,
        text_output=True,
        image_input=False,
        file_input=False,
        tools=True,
        parallel_tool_calls=True,
        tool_choice_modes=frozenset({"auto", "none", "required"}),
        reasoning_levels=(),
        context_token_budget=resolve_context_token_budget(
            ProviderName.CLIPROXY, model_id
        ),
        max_output_tokens=16_384,
        omit_settings=frozenset(
            {
                "previous_response_id",
                "openai_previous_response_id",
            }
        ),
        reject_settings=frozenset({"image_input", "file_input"}),
    )


def profile_for(provider: ProviderName, model_id: str) -> ProviderProfile:
    if provider is ProviderName.DEEPSEEK:
        if model_id != DEEPSEEK_MODEL_ID:
            # Still return DeepSeek profile shape; selection validation happens elsewhere
            return DEEPSEEK_PROFILE
        return DEEPSEEK_PROFILE
    return cliproxy_profile(model_id)
