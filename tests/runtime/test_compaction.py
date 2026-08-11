"""History compaction complete units."""

from __future__ import annotations

import json

from typed_code.compaction import ModelMessageRecord, compact_messages


def _msg(
    pos: int,
    role: str,
    text: str,
    *,
    run_id: str | None = None,
    part_kind: str | None = None,
) -> ModelMessageRecord:
    part = {"content": text * 803}
    if part_kind is not None:
        part["part_kind"] = part_kind
    payload = json.dumps([{"kind": "request", "parts": [part]}])
    return ModelMessageRecord(
        id=f"id-{pos}",
        session_id="s",
        run_id=run_id,
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



def test_compaction_keeps_tool_call_and_return_in_the_same_run_unit() -> None:
    messages = [
        _msg(1, "user", "prompt", run_id="r1", part_kind="user-prompt"),
        _msg(2, "assistant", "call", run_id="r1", part_kind="tool-call"),
        _msg(3, "user", "result", run_id="r1", part_kind="tool-return"),
        _msg(4, "assistant", "answer", run_id="r1", part_kind="text"),
        _msg(5, "user", "next", run_id="r2", part_kind="user-prompt"),
        _msg(6, "assistant", "done", run_id="r2", part_kind="text"),
    ]

    result = compact_messages(messages, token_budget=80, output_reserve=0)

    assert [message.id for message in result.kept] == ["id-5", "id-6"]
    assert result.removed_item_count == 4