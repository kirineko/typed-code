"""Token budget estimation for context compaction.

Aligned with reference implementations:

- **deepy** (``deepy.llm.context``): prefer ``tiktoken`` ``cl100k_base``; fall back to
  ``ceil(len/4)``; walk structured items; fixed cost for image parts.
- **pi** (``estimateTokens`` / ``estimateContextTokens``): content-aware char counts
  for text/thinking/tool arguments (then chars/4); prefer last provider usage as an
  anchor and only *estimate* messages after that checkpoint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import ceil
from types import ModuleType
from typing import Any

# deepy: fixed per-image part budget when modality appears in content lists
_IMAGE_PART_TOKENS = 1024
# pi: ESTIMATED_IMAGE_CHARS = 4800 → ~1200 tokens at chars/4; we keep deepy's 1024
# for part-level counting so multimodal rows stay conservative but not extreme.

_ENCODING: Any | None = None
_ENCODING_FAILED = False
_tiktoken_mod: ModuleType | None
try:
    import tiktoken as _tiktoken_imported

    _tiktoken_mod = _tiktoken_imported
except Exception:  # pragma: no cover - optional at import time
    _tiktoken_mod = None


def estimate_tokens(text: str) -> int:
    """Estimate tokens for plain text (tiktoken preferred, chars/4 fallback)."""
    if not text:
        return 0
    encoding = _token_encoding()
    if encoding is not None:
        try:
            return max(1, len(encoding.encode(text)))
        except Exception:  # pragma: no cover - defensive
            pass
    return max(1, ceil(len(text) / 4))


def estimate_json_tokens(payload_json: str) -> int:
    """Estimate tokens for a stored JSON payload (model message or transcript).

    Parses JSON when possible and walks the structure so we count *content*
    rather than raw serialization noise (quotes, keys repeated everywhere).
    """
    if not payload_json:
        return 0
    try:
        data = json.loads(payload_json)
    except json.JSONDecodeError:
        return estimate_tokens(payload_json)
    return estimate_tokens_for_item(data)


def estimate_tokens_for_item(item: Any) -> int:
    """Structure-aware estimate for history items (deepy-style)."""
    if item is None:
        return 0
    if isinstance(item, str):
        return estimate_tokens(item)
    if isinstance(item, (int, float, bool)):
        return estimate_tokens(str(item))
    if isinstance(item, list):
        total = sum(estimate_tokens_for_item(part) for part in item)
        return max(total, 1) if item else 0
    if isinstance(item, dict):
        return _estimate_mapping(item)
    return estimate_tokens(str(item))


def estimate_tokens_for_items(items: list[Any]) -> int:
    return sum(estimate_tokens_for_item(item) for item in items)


@dataclass(frozen=True)
class ContextUsageEstimate:
    """Hybrid context size (pi ``estimateContextTokens`` analogue)."""

    tokens: int
    usage_tokens: int
    trailing_tokens: int
    last_usage_index: int | None


def estimate_context_tokens(
    payloads: list[str],
    *,
    last_usage_tokens: int | None = None,
    last_usage_index: int | None = None,
) -> ContextUsageEstimate:
    """Estimate total context size for ordered message payloads.

    When ``last_usage_tokens`` and ``last_usage_index`` are provided (provider
    usage checkpoint through that inclusive index), tokens after the checkpoint
    are estimated and added — matching pi's usage-anchor + trailing estimate.
    """
    if not payloads:
        return ContextUsageEstimate(
            tokens=0, usage_tokens=0, trailing_tokens=0, last_usage_index=None
        )

    pure_estimated = sum(estimate_json_tokens(p) for p in payloads)

    if (
        last_usage_tokens is None
        or last_usage_index is None
        or last_usage_index < 0
        or last_usage_index >= len(payloads)
    ):
        return ContextUsageEstimate(
            tokens=pure_estimated,
            usage_tokens=0,
            trailing_tokens=pure_estimated,
            last_usage_index=None,
        )

    trailing = sum(
        estimate_json_tokens(payloads[i])
        for i in range(last_usage_index + 1, len(payloads))
    )
    checkpoint = last_usage_tokens + trailing
    active = repair_undercounted_context_tokens(checkpoint, pure_estimated)

    return ContextUsageEstimate(
        tokens=active,
        usage_tokens=last_usage_tokens,
        trailing_tokens=trailing,
        last_usage_index=last_usage_index,
    )


# deepy store_helpers.repair_undercounted_context_tokens
CONTEXT_UNDERCOUNT_REPAIR_RATIO = 2
CONTEXT_UNDERCOUNT_REPAIR_MIN_DELTA = 128


def repair_undercounted_context_tokens(
    checkpoint_tokens: int, estimated_tokens: int
) -> int:
    """Prefer full estimate when the usage checkpoint is badly undercounted."""
    if estimated_tokens <= checkpoint_tokens:
        return checkpoint_tokens
    if (
        estimated_tokens - checkpoint_tokens >= CONTEXT_UNDERCOUNT_REPAIR_MIN_DELTA
        and estimated_tokens >= checkpoint_tokens * CONTEXT_UNDERCOUNT_REPAIR_RATIO
    ):
        return estimated_tokens
    return checkpoint_tokens


def _estimate_mapping(item: dict[str, Any]) -> int:
    # Multimodal content lists: deepy-style fixed image part cost
    if _looks_like_image_item(item):
        return _estimate_multimodal_item_tokens(item)

    # pi-style content-aware paths for common agent message shapes
    content_tokens = _estimate_content_field(item)
    if content_tokens is not None:
        # Still account for lightweight role/kind overhead
        overhead = 0
        for key in ("role", "kind", "type", "name", "tool_name"):
            value = item.get(key)
            if isinstance(value, str) and value:
                overhead += estimate_tokens(value)
        return max(content_tokens + overhead, 1)

    # Generic walk: prefer text-bearing values over dumping entire JSON
    tokens = 0
    for key, value in item.items():
        if key in {"id", "run_id", "conversation_id", "timestamp", "created_at"}:
            continue
        if key in {"usage", "provider_details", "provider_response_id"}:
            continue
        tokens += estimate_tokens_for_item(value)
    return max(tokens, 1) if item else 0


def _estimate_content_field(item: dict[str, Any]) -> int | None:
    """Return tokens for known content layouts, or None to fall back."""
    # Assistant / user multimodal content list
    content = item.get("content")
    if isinstance(content, str):
        return estimate_tokens(content)
    if isinstance(content, list):
        return _estimate_content_blocks(content)

    # PAI parts array (ModelRequest / ModelResponse)
    parts = item.get("parts")
    if isinstance(parts, list):
        return sum(_estimate_part(part) for part in parts)

    # Tool result / bash-like shapes
    for key in ("output", "summary", "text", "thinking", "arguments"):
        if key in item and item[key] is not None:
            break
    else:
        return None

    total = 0
    saw = False
    for key in ("output", "summary", "text", "thinking", "command", "name"):
        value = item.get(key)
        if isinstance(value, str) and value:
            total += estimate_tokens(value)
            saw = True
    args = item.get("arguments")
    if args is not None:
        total += estimate_tokens_for_item(args)
        saw = True
    return total if saw else None


def _estimate_content_blocks(blocks: list[Any]) -> int:
    tokens = 0
    for block in blocks:
        if isinstance(block, str):
            tokens += estimate_tokens(block)
            continue
        if not isinstance(block, dict):
            tokens += estimate_tokens_for_item(block)
            continue
        tokens += _estimate_part(block)
    return max(tokens, 1) if blocks else 0


def _estimate_part(part: Any) -> int:
    if not isinstance(part, dict):
        return estimate_tokens_for_item(part)

    part_type = str(part.get("type") or part.get("part_kind") or "")

    if part_type in {
        "input_image",
        "image",
        "image_url",
        "output_image",
    } or "image_url" in part:
        return _IMAGE_PART_TOKENS

    # Text-like
    for key in ("text", "content", "thinking", "summary"):
        value = part.get(key)
        if isinstance(value, str) and value:
            return estimate_tokens(value)
        if isinstance(value, list):
            return _estimate_content_blocks(value)

    # Tool call: name + arguments (pi toolCall path)
    if part_type in {"toolCall", "tool_call", "function_call", "tool-call"} or (
        "name" in part and ("arguments" in part or "args" in part)
    ):
        chars_proxy = 0
        name = part.get("name") or part.get("tool_name")
        if isinstance(name, str):
            chars_proxy += len(name)
        args = part.get("arguments", part.get("args"))
        if args is not None:
            if isinstance(args, str):
                chars_proxy += len(args)
            else:
                try:
                    chars_proxy += len(json.dumps(args, ensure_ascii=False, default=str))
                except TypeError:
                    chars_proxy += len(str(args))
        if chars_proxy:
            encoding = _token_encoding()
            if encoding is not None:
                return max(1, estimate_tokens_for_item(name) + estimate_tokens_for_item(args))
            return max(1, ceil(chars_proxy / 4))

    # user-prompt / tool-return etc. with nested content
    if "content" in part:
        return estimate_tokens_for_item(part["content"])

    return estimate_tokens_for_item(
        {k: v for k, v in part.items() if k not in {"id", "timestamp", "provider_details"}}
    )


def _looks_like_image_item(item: dict[str, Any]) -> bool:
    content = item.get("content")
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype in {"input_image", "image", "image_url", "output_image"} or "image_url" in part:
            return True
    return False


def _estimate_multimodal_item_tokens(item: dict[str, Any]) -> int:
    content = item.get("content")
    if not isinstance(content, list):
        return estimate_tokens(json.dumps(item, ensure_ascii=False, default=str))
    tokens = 0
    for part in content:
        if not isinstance(part, dict):
            tokens += estimate_tokens_for_item(part)
            continue
        ptype = part.get("type")
        if ptype in {"input_image", "image", "image_url", "output_image"} or "image_url" in part:
            tokens += _IMAGE_PART_TOKENS
            continue
        tokens += _estimate_part(part)
    return max(tokens, 1)


def _token_encoding() -> Any | None:
    """Lazy-load tiktoken cl100k_base (same encoding deepy uses)."""
    global _ENCODING, _ENCODING_FAILED
    if _ENCODING is not None:
        return _ENCODING
    if _ENCODING_FAILED or _tiktoken_mod is None:
        return None
    try:
        _ENCODING = _tiktoken_mod.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover
        _ENCODING_FAILED = True
        return None
    return _ENCODING


def reset_encoding_cache() -> None:
    """Test helper to clear the cached encoder."""
    global _ENCODING, _ENCODING_FAILED
    _ENCODING = None
    _ENCODING_FAILED = False
