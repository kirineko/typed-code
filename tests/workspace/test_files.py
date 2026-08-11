"""File read/write/edit tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from typed_code.workspace.errors import EditConflictError, EncodingError
from typed_code.workspace.files import edit_text_file, read_text_file, write_text_file
from typed_code.workspace.paths import normalize_workspace_root


def test_read_write_roundtrip(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    write_text_file(root, "src/a.py", "hello\n")
    result = read_text_file(root, "src/a.py", max_bytes=1000, max_lines=100)
    assert result.content == "hello\n"
    assert result.truncation.truncated is False


def test_read_truncation(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    write_text_file(root, "big.txt", "line\n" * 50)
    result = read_text_file(root, "big.txt", max_bytes=10_000, max_lines=5)
    assert result.truncation.truncated is True
    assert result.content.count("\n") <= 5


def test_edit_unique_and_conflict(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    write_text_file(root, "f.txt", "aaa bbb aaa\n")
    with pytest.raises(EditConflictError, match="unique"):
        edit_text_file(root, "f.txt", old_string="aaa", new_string="x")

    write_text_file(root, "g.txt", "only once\n")
    edited = edit_text_file(root, "g.txt", old_string="only once", new_string="twice")
    assert "twice" in edited.diff
    assert (root / "g.txt").read_text(encoding="utf-8") == "twice\n"

    with pytest.raises(EditConflictError, match="not found"):
        edit_text_file(root, "g.txt", old_string="missing", new_string="x")
    assert (root / "g.txt").read_text(encoding="utf-8") == "twice\n"


def test_encoding_error(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    (root / "bin.dat").write_bytes(b"\xff\xfe\x00\x01")
    with pytest.raises(EncodingError):
        read_text_file(root, "bin.dat", max_bytes=100, max_lines=10)
