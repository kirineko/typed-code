"""Bounded workspace file read/write/edit."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

from typed_code.workspace.bounds import TruncationInfo, truncate_text
from typed_code.workspace.errors import (
    EditConflictError,
    EncodingError,
    FileNotFoundWorkspaceError,
)
from typed_code.workspace.paths import display_path, resolve_in_workspace


@dataclass(frozen=True)
class ReadResult:
    path: str
    content: str
    size_bytes: int
    encoding: str
    truncation: TruncationInfo


@dataclass(frozen=True)
class WriteResult:
    path: str
    size_bytes: int
    created: bool


@dataclass(frozen=True)
class EditResult:
    path: str
    diff: str
    replacements: int


def read_text_file(
    workspace: Path,
    user_path: str,
    *,
    max_bytes: int,
    max_lines: int,
) -> ReadResult:
    target = resolve_in_workspace(workspace, user_path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundWorkspaceError(f"file not found: {user_path}")

    raw = target.read_bytes()
    try:
        text = raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError as exc:
        raise EncodingError(
            f"file is not valid UTF-8 text: {user_path} ({exc.reason})"
        ) from exc

    content, truncation = truncate_text(text, max_bytes=max_bytes, max_lines=max_lines)
    return ReadResult(
        path=display_path(workspace, target),
        content=content,
        size_bytes=len(raw),
        encoding=encoding,
        truncation=truncation,
    )


def write_text_file(workspace: Path, user_path: str, content: str) -> WriteResult:
    target = resolve_in_workspace(workspace, user_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    created = not target.exists()
    data = content.encode("utf-8")
    _atomic_write(target, data)
    return WriteResult(
        path=display_path(workspace, target),
        size_bytes=len(data),
        created=created,
    )


def edit_text_file(
    workspace: Path,
    user_path: str,
    *,
    old_string: str,
    new_string: str,
    max_diff_bytes: int = 64_000,
) -> EditResult:
    target = resolve_in_workspace(workspace, user_path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundWorkspaceError(f"file not found: {user_path}")

    try:
        original = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EncodingError(f"file is not valid UTF-8 text: {user_path}") from exc

    if old_string == "":
        raise EditConflictError("old_string must be non-empty")

    count = original.count(old_string)
    if count == 0:
        raise EditConflictError(
            "edit precondition failed: old_string not found in file"
        )
    if count > 1:
        raise EditConflictError(
            f"edit precondition failed: old_string matches {count} times; must be unique"
        )

    updated = original.replace(old_string, new_string, 1)
    _atomic_write(target, updated.encode("utf-8"))

    diff_lines = list(
        unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{display_path(workspace, target)}",
            tofile=f"b/{display_path(workspace, target)}",
        )
    )
    diff = "".join(diff_lines)
    if len(diff.encode("utf-8")) > max_diff_bytes:
        diff = diff.encode("utf-8")[:max_diff_bytes].decode("utf-8", errors="ignore")
        diff += "\n... [diff truncated]\n"

    return EditResult(path=display_path(workspace, target), diff=diff, replacements=1)


def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
