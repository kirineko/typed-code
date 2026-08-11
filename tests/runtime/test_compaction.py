"""History compaction complete units."""

from __future__ import annotations

import json

from typed_code.compaction import ModelMessageRecord, compact_messages


def _msg(pos: int, role: str, text: str) -> ModelMessageRecord:
    # Store PAI-like JSON so structure-aware estimation applies
    payload = json.dumps({"kind": "request" if role == "user" else "response",
                          "parts": [{"content": text * 80}]})
    return ModelMessageRecord(
        id=f"id-{pos}",
        session_id="s",
        run_id=None,
        position=pos,
        role=role,
        payload_json=payload,
        created_at="t",
    )


def test_compact_drops_oldest_units() -> None:
    messages = [
        _msg(1, "user", "U1"),
        _msg(2, "assistant", "A1"),
        _msg(3, "user", "U2"),
        _msg(4, "assistant", "A2"),
        _msg(5, "user", "U3"),
        _msg(6, "assistant", "A3"),
    ]
    result = compact_messages(messages, token_budget=80, output_reserve=0)
    assert result.removed_item_count > 0
    assert result.kept
    # Newest user unit retained
    assert any("U3" in m.payload_json for m in result.kept)
    assert result.estimated_tokens_after <= 80 or len(result.kept) <= 4
