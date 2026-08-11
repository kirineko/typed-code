"""Explicit OpenAIResponsesModel factories (no Chat Completions)."""

from __future__ import annotations

import httpx
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.providers.openai import OpenAIProvider

from typed_code.protocol.common import ProviderName
from typed_code.providers.catalog import ResolvedModel
from typed_code.providers.profiles import DEEPSEEK_MODEL_ID


def build_responses_model(
    resolved: ResolvedModel,
    *,
    api_key: str,
    http_client: httpx.AsyncClient | None = None,
) -> OpenAIResponsesModel:
    """Construct an explicit Responses model. Never returns a Chat Completions model."""
    if resolved.provider is ProviderName.DEEPSEEK:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=resolved.base_url.rstrip("/"),
            http_client=http_client,
        )
        provider = DeepSeekProvider(openai_client=client)
        return OpenAIResponsesModel(
            model_name=DEEPSEEK_MODEL_ID,
            provider=provider,
        )

    provider = OpenAIProvider(
        api_key=api_key,
        base_url=resolved.base_url.rstrip("/"),
        http_client=http_client,
    )
    return OpenAIResponsesModel(
        model_name=resolved.model_id,
        provider=provider,
    )


def assert_responses_only(model: object) -> OpenAIResponsesModel:
    if not isinstance(model, OpenAIResponsesModel):
        raise TypeError(
            f"expected OpenAIResponsesModel, got {type(model).__name__}; "
            "Chat Completions models are not permitted"
        )
    return model
