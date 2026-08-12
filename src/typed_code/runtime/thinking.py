"""Normalize Pydantic AI thinking parts, including provider-native CoT fields."""

from __future__ import annotations

from typing import Any

from pydantic_ai import ThinkingPart, ThinkingPartDelta


def thinking_text(part: ThinkingPart) -> str:
    """Return displayable reasoning, preferring the longer native CoT payload."""
    content = part.content or ""
    raw = raw_content_text(part.provider_details)
    return raw if len(raw) > len(content) else content


def prefer_thinking_text(part: ThinkingPart, accumulated: str) -> str:
    """Keep the longer of streamed accumulation and the ended part payload."""
    text = thinking_text(part)
    return accumulated if len(accumulated) > len(text) else text


def apply_thinking_delta(
    part: ThinkingPart, delta: ThinkingPartDelta
) -> tuple[ThinkingPart, str]:
    """Apply a thinking delta and return the updated part plus new display text."""
    previous = thinking_text(part)
    try:
        updated = delta.apply(part)
    except ValueError:
        return part, ""
    current = thinking_text(updated)
    if current.startswith(previous):
        return updated, current[len(previous) :]
    if current and current != previous:
        return updated, current
    return updated, ""


def raw_content_text(details: Any) -> str:
    if not isinstance(details, dict):
        return ""
    raw = details.get("raw_content")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "".join(item for item in raw if isinstance(item, str))
    return ""
