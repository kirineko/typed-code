"""Complete-unit history compaction."""

from __future__ import annotations

import json
from dataclasses import dataclass

from typed_code.compaction.budget import (
    ContextUsageEstimate,
    estimate_context_tokens,
    estimate_json_tokens,
)


@dataclass(frozen=True)
class ModelMessageRecord:
    id: str
    session_id: str
    run_id: str | None
    position: int
    role: str
    payload_json: str
    created_at: str


@dataclass(frozen=True)
class CompactionResult:
    kept: list[ModelMessageRecord]
    removed: list[ModelMessageRecord]
    removed_item_count: int
    estimated_tokens_before: int
    estimated_tokens_after: int
    usage_estimate: ContextUsageEstimate | None = None


def compact_messages(
    messages: list[ModelMessageRecord],
    *,
    token_budget: int,
    output_reserve: int = 2048,
    last_usage_tokens: int | None = None,
    last_usage_index: int | None = None,
) -> CompactionResult:
    """Drop oldest complete units until under budget.

    A complete unit is a contiguous block starting at a ``user`` role message
    through the next messages until the following ``user`` (exclusive).

    Token counts use structure-aware estimation (tiktoken when available). When
    provider usage is known, pass ``last_usage_*`` so size follows the pi/deepy
    hybrid: usage checkpoint + estimated trailing messages.
    """
    if token_budget < 1:
        raise ValueError("token_budget must be >= 1")

    limit = max(1, token_budget - max(0, output_reserve))
    payloads = [m.payload_json for m in messages]
    usage_estimate = estimate_context_tokens(
        payloads,
        last_usage_tokens=last_usage_tokens,
        last_usage_index=last_usage_index,
    )
    before = usage_estimate.tokens
    if before <= limit or not messages:
        return CompactionResult(
            kept=list(messages),
            removed=[],
            removed_item_count=0,
            estimated_tokens_before=before,
            estimated_tokens_after=before,
            usage_estimate=usage_estimate,
        )

    units = _split_units(messages)
    removed: list[ModelMessageRecord] = []
    remaining_units = list(units)

    def total(units_list: list[list[ModelMessageRecord]]) -> int:
        unit_payloads = [m.payload_json for u in units_list for m in u]
        # After drops, usage checkpoint may no longer align; pure estimate is safer.
        return sum(estimate_json_tokens(p) for p in unit_payloads)

    while len(remaining_units) > 1 and total(remaining_units) > limit:
        dropped = remaining_units.pop(0)
        removed.extend(dropped)

    kept = [m for u in remaining_units for m in u]
    after = total(remaining_units) if remaining_units else 0
    return CompactionResult(
        kept=kept,
        removed=removed,
        removed_item_count=len(removed),
        estimated_tokens_before=before,
        estimated_tokens_after=after,
        usage_estimate=usage_estimate,
    )


def _split_units(messages: list[ModelMessageRecord]) -> list[list[ModelMessageRecord]]:
    if not messages:
        return []
    units: list[list[ModelMessageRecord]] = []
    current: list[ModelMessageRecord] = []
    current_run_id: str | None = None
    for msg in messages:
        run_changed = (
            bool(current)
            and msg.run_id != current_run_id
            and (msg.run_id is not None or current_run_id is not None)
        )
        legacy_user_boundary = (
            bool(current)
            and msg.run_id is None
            and current_run_id is None
            and _starts_user_turn(msg)
        )
        if run_changed or legacy_user_boundary:
            units.append(current)
            current = []
        current.append(msg)
        current_run_id = msg.run_id
    if current:
        units.append(current)
    return units


def _starts_user_turn(message: ModelMessageRecord) -> bool:
    """Distinguish a user prompt request from tool-return request messages."""
    if message.role != "user":
        return False
    try:
        payload = json.loads(message.payload_json)
    except json.JSONDecodeError:
        return True
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return True
    parts = payload.get("parts")
    if not isinstance(parts, list):
        return True

    kinds = {
        str(part.get("part_kind") or part.get("type") or "")
        for part in parts
        if isinstance(part, dict)
    }
    if kinds.intersection(
        {"tool-return", "retry-prompt", "tool-search-return", "capability-load-return"}
    ):
        return False
    return "user-prompt" in kinds or not (kinds - {""})
