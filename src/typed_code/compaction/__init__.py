"""Context budgeting and complete-unit history compaction."""

from __future__ import annotations

from typed_code.compaction.budget import (
    ContextUsageEstimate,
    estimate_context_tokens,
    estimate_json_tokens,
    estimate_tokens,
    estimate_tokens_for_item,
    estimate_tokens_for_items,
    repair_undercounted_context_tokens,
)
from typed_code.compaction.compact import CompactionResult, ModelMessageRecord, compact_messages

__all__ = [
    "CompactionResult",
    "ContextUsageEstimate",
    "ModelMessageRecord",
    "compact_messages",
    "estimate_context_tokens",
    "estimate_json_tokens",
    "estimate_tokens",
    "estimate_tokens_for_item",
    "estimate_tokens_for_items",
    "repair_undercounted_context_tokens",
]
