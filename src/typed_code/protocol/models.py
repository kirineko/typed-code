"""Public model catalog metadata (no credentials)."""

from __future__ import annotations

from typed_code.protocol.common import (
    ProtocolModel,
    ProviderAvailability,
    ProviderName,
)


class ModelCapabilities(ProtocolModel):
    """Minimal capability summary exposed to clients."""

    text_input: bool = True
    text_output: bool = True
    image_input: bool = False
    tools: bool = True
    parallel_tool_calls: bool = True
    web_search: bool = False
    reasoning_levels: list[str] = []
    default_reasoning_level: str | None = None


class ModelInfo(ProtocolModel):
    provider: ProviderName
    model_id: str
    display_name: str | None = None
    availability: ProviderAvailability
    capabilities: ModelCapabilities = ModelCapabilities()
    context_token_budget: int = 128_000


class ModelListResponse(ProtocolModel):
    models: list[ModelInfo]
