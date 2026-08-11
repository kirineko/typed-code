"""Load and serialize Pydantic AI model messages (runtime-private)."""

from __future__ import annotations

from typing import Any

from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

from typed_code.compaction.compact import ModelMessageRecord
from typed_code.domain.transitions import ModelMessageDraft


def dumps_messages(messages: list[ModelMessage]) -> list[ModelMessageDraft]:
    """Serialize each ModelMessage as its own JSON row payload."""
    drafts: list[ModelMessageDraft] = []
    for msg in messages:
        payload = ModelMessagesTypeAdapter.dump_json([msg]).decode("utf-8")
        role = _role_for(msg)
        drafts.append(ModelMessageDraft(role=role, payload_json=payload, run_id=None))
    return drafts


def loads_messages(records: list[ModelMessageRecord]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for record in records:
        batch = ModelMessagesTypeAdapter.validate_json(record.payload_json)
        messages.extend(batch)
    return messages


def dumps_message_list_json(messages: list[ModelMessage]) -> str:
    return ModelMessagesTypeAdapter.dump_json(messages).decode("utf-8")


def _role_for(msg: Any) -> str:
    kind = getattr(msg, "kind", None)
    if kind == "request":
        return "user"
    if kind == "response":
        return "assistant"
    return str(kind or "unknown")
