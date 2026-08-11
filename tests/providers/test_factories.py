"""Responses model factories."""

from __future__ import annotations

from pydantic_ai.models.openai import OpenAIResponsesModel

from typed_code.config.credentials import ProviderAvailability
from typed_code.protocol.common import ProviderName
from typed_code.providers.catalog import ResolvedModel
from typed_code.providers.factories import assert_responses_only, build_responses_model
from typed_code.providers.profiles import DEEPSEEK_MODEL_ID


def test_build_deepseek_responses_model() -> None:
    resolved = ResolvedModel(
        provider=ProviderName.DEEPSEEK,
        model_id=DEEPSEEK_MODEL_ID,
        base_url="https://api.deepseek.com",
        display_name="DeepSeek",
        availability=ProviderAvailability.AVAILABLE,
    )
    model = build_responses_model(resolved, api_key="secret")
    assert isinstance(model, OpenAIResponsesModel)
    assert assert_responses_only(model) is model
    assert model.model_name == DEEPSEEK_MODEL_ID


def test_build_cliproxy_responses_model() -> None:
    resolved = ResolvedModel(
        provider=ProviderName.CLIPROXY,
        model_id="gpt-5.6-sol",
        base_url="http://127.0.0.1:8317/v1",
        display_name="gpt-5.6-sol",
        availability=ProviderAvailability.AVAILABLE,
    )
    model = build_responses_model(resolved, api_key="secret")
    assert isinstance(model, OpenAIResponsesModel)
    assert model.model_name == "gpt-5.6-sol"
