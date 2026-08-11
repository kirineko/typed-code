"""Bounded text/byte capture helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TruncationInfo:
    truncated: bool
    original_bytes: int
    captured_bytes: int
    original_lines: int | None = None
    captured_lines: int | None = None
    direction: str = "end"


def truncate_text(
    text: str,
    *,
    max_bytes: int,
    max_lines: int | None = None,
) -> tuple[str, TruncationInfo]:
    raw = text.encode("utf-8")
    original_bytes = len(raw)
    lines = text.splitlines(keepends=True)
    original_lines = len(lines)

    truncated = False
    out_lines = lines
    if max_lines is not None and max_lines > 0 and len(out_lines) > max_lines:
        out_lines = out_lines[:max_lines]
        truncated = True

    out = "".join(out_lines)
    encoded = out.encode("utf-8")
    if max_bytes > 0 and len(encoded) > max_bytes:
        encoded = encoded[:max_bytes]
        # Avoid splitting multibyte sequences
        out = encoded.decode("utf-8", errors="ignore")
        truncated = True

    captured = out.encode("utf-8")
    return out, TruncationInfo(
        truncated=truncated,
        original_bytes=original_bytes,
        captured_bytes=len(captured),
        original_lines=original_lines,
        captured_lines=len(out.splitlines()) if out else 0,
        direction="end",
    )


def truncate_bytes(data: bytes, *, max_bytes: int) -> tuple[bytes, TruncationInfo]:
    original = len(data)
    if max_bytes > 0 and original > max_bytes:
        captured = data[:max_bytes]
        return captured, TruncationInfo(
            truncated=True,
            original_bytes=original,
            captured_bytes=len(captured),
            direction="end",
        )
    return data, TruncationInfo(
        truncated=False,
        original_bytes=original,
        captured_bytes=original,
        direction="end",
    )
