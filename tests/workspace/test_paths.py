"""Workspace path confinement tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from typed_code.workspace.errors import PathEscapeError
from typed_code.workspace.paths import normalize_workspace_root, resolve_in_workspace


def test_resolve_inside(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    (root / "a.txt").write_text("x", encoding="utf-8")
    resolved = resolve_in_workspace(root, "a.txt")
    assert resolved == root / "a.txt"


def test_reject_parent_traversal(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    with pytest.raises(PathEscapeError):
        resolve_in_workspace(root, "../secret")


def test_reject_symlink_escape(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    outside = tmp_path.parent / "outside-file"
    outside.write_text("nope", encoding="utf-8")
    link = root / "link"
    link.symlink_to(outside)
    with pytest.raises(PathEscapeError):
        resolve_in_workspace(root, "link")
