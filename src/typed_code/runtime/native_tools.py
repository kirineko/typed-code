"""Provider-native Responses tools (not workspace function tools)."""

from __future__ import annotations

from typing import Any

from pydantic_ai.capabilities import NativeTool
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.native_tools import WebSearchTool

from typed_code.config.settings import Settings
from typed_code.providers.profiles import ProviderProfile

NATIVE_WEB_SEARCH_NAME = "web_search"
_QUERY_PREVIEW_LIMIT = 80


def native_web_search_enabled(
    settings: Settings,
    profile: ProviderProfile,
    model: Model | None = None,
) -> bool:
    if not settings.native_web_search or not profile.native_web_search:
        return False
    if model is None:
        return True
    return isinstance(model, OpenAIResponsesModel)


def native_web_search_capabilities(enabled: bool) -> list[NativeTool[Any]]:
    if not enabled:
        return []
    return [NativeTool(WebSearchTool())]


def web_search_call_summary(args: object) -> str:
    query = _query_from_args(args)
    if not query:
        return "web search"
    preview = " ".join(query.split())
    if len(preview) > _QUERY_PREVIEW_LIMIT:
        preview = preview[: _QUERY_PREVIEW_LIMIT - 1] + "…"
    return f"search {preview}"


def web_search_result_summary(content: object, *, ok: bool) -> str:
    if not ok:
        return "web search failed"
    if isinstance(content, dict):
        sources = content.get("sources")
        if isinstance(sources, list) and sources:
            return f"search completed ({len(sources)} sources)"
        status = content.get("status")
        if isinstance(status, str) and status and status != "completed":
            return f"search {status}"
    return "search completed"


def _query_from_args(args: object) -> str | None:
    if isinstance(args, str) and args.strip():
        return args.strip()
    if not isinstance(args, dict):
        return None
    query = args.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()
    queries = args.get("queries")
    if isinstance(queries, list):
        parts = [item.strip() for item in queries if isinstance(item, str) and item.strip()]
        if parts:
            return "; ".join(parts)
    return None
