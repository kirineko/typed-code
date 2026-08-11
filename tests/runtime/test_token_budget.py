"""Token estimation aligned with deepy/pi reference behavior."""

from __future__ import annotations

import json

from typed_code.compaction.budget import (
    estimate_context_tokens,
    estimate_json_tokens,
    estimate_tokens,
    estimate_tokens_for_item,
    reset_encoding_cache,
)


def test_empty_text_is_zero() -> None:
    assert estimate_tokens("") == 0


def test_plain_text_positive() -> None:
    n = estimate_tokens("hello world")
    assert n >= 1


def test_tiktoken_preferred_when_available() -> None:
    reset_encoding_cache()
    text = "The quick brown fox jumps over the lazy dog."
    n = estimate_tokens(text)
    # cl100k_base encodes this short English sentence to a small fixed count
    try:
        import tiktoken

        expected = len(tiktoken.get_encoding("cl100k_base").encode(text))
        assert n == max(1, expected)
    except Exception:
        # Fallback path: chars/4
        assert n == max(1, (len(text) + 3) // 4)


def test_structured_item_counts_content_not_only_json_keys() -> None:
    body = "x" * 400
    payload = json.dumps(
        {
            "kind": "response",
            "parts": [{"part_kind": "text", "content": body}],
        }
    )
    structured = estimate_json_tokens(payload)
    naive = max(1, (len(payload) + 3) // 4)
    # Content-aware path should be closer to text length than full JSON dump
    text_only = estimate_tokens(body)
    assert structured >= text_only
    # And should not explode far above text-only the way raw JSON key noise can
    assert structured <= naive


def test_image_part_fixed_cost_like_deepy() -> None:
    item = {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "see image"},
            {"type": "input_image", "image_url": "https://example.com/a.png"},
        ],
    }
    tokens = estimate_tokens_for_item(item)
    assert tokens >= 1024


def test_tool_call_counts_name_and_arguments_like_pi() -> None:
    item = {
        "role": "assistant",
        "content": [
            {
                "type": "toolCall",
                "name": "edit",
                "arguments": {"path": "a.py", "old": "a" * 100, "new": "b" * 100},
            }
        ],
    }
    tokens = estimate_tokens_for_item(item)
    assert tokens >= 20


def test_context_usage_anchor_plus_trailing_like_pi() -> None:
    payloads = [
        json.dumps({"parts": [{"content": "a" * 40}]}),
        json.dumps({"parts": [{"content": "b" * 40}]}),
        json.dumps({"parts": [{"content": "c" * 80}]}),
    ]
    pure = estimate_context_tokens(payloads)
    assert pure.last_usage_index is None
    assert pure.tokens == pure.trailing_tokens

    hybrid = estimate_context_tokens(
        payloads,
        last_usage_tokens=50,
        last_usage_index=1,  # usage covers first two messages
    )
    assert hybrid.last_usage_index == 1
    assert hybrid.usage_tokens == 50
    # trailing is only the third payload
    assert hybrid.trailing_tokens == estimate_json_tokens(payloads[2])
    assert hybrid.tokens == 50 + hybrid.trailing_tokens


def test_repair_undercounted_matches_deepy_thresholds() -> None:
    from typed_code.compaction.budget import repair_undercounted_context_tokens

    # Small delta: keep checkpoint
    assert repair_undercounted_context_tokens(100, 150) == 100
    # Large absolute + 2x ratio: prefer estimate
    assert repair_undercounted_context_tokens(100, 300) == 300


def test_invalid_json_falls_back_to_text() -> None:
    raw = "not-json {" + ("z" * 20)
    assert estimate_json_tokens(raw) == estimate_tokens(raw)
