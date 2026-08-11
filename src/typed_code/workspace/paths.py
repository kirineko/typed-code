"""Workspace path resolution and confinement."""

from __future__ import annotations

import os
from pathlib import Path

from typed_code.workspace.errors import PathEscapeError


def normalize_workspace_root(workspace: Path | str) -> Path:
    root = Path(workspace).expanduser()
    if not root.is_absolute():
        root = (Path.cwd() / root).resolve()
    else:
        root = root.resolve()
    if not root.exists():
        raise PathEscapeError(f"workspace does not exist: {root}")
    if not root.is_dir():
        raise PathEscapeError(f"workspace is not a directory: {root}")
    return root


def resolve_in_workspace(workspace: Path, user_path: str) -> Path:
    """Resolve ``user_path`` under workspace; reject parent traversal and symlink escape."""
    if not user_path or "\x00" in user_path:
        raise PathEscapeError("path must be a non-empty string without null bytes")

    root = workspace.resolve()
    candidate = Path(user_path)
    if candidate.is_absolute():
        # Absolute paths must still resolve inside the workspace.
        target = candidate
    else:
        target = root / candidate

    # Walk parents to reject symlink escapes before final resolve when possible.
    try:
        resolved = target.resolve(strict=False)
    except OSError as exc:
        raise PathEscapeError(f"failed to resolve path: {exc}") from exc

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathEscapeError(
            f"path escapes workspace boundary: {user_path!r}"
        ) from exc

    # If the path exists, ensure the real path (after symlinks) stays inside.
    if resolved.exists() or resolved.is_symlink():
        real = Path(os.path.realpath(resolved))
        try:
            real.relative_to(Path(os.path.realpath(root)))
        except ValueError as exc:
            raise PathEscapeError(
                f"path resolves outside workspace via symlink: {user_path!r}"
            ) from exc
        return real if resolved.exists() else resolved

    # For not-yet-existing paths, ensure each existing parent stays confined.
    parent = resolved.parent
    while True:
        if parent.exists() or parent.is_symlink():
            real_parent = Path(os.path.realpath(parent))
            try:
                real_parent.relative_to(Path(os.path.realpath(root)))
            except ValueError as exc:
                raise PathEscapeError(
                    f"path parent escapes workspace: {user_path!r}"
                ) from exc
            break
        if parent == root or parent == parent.parent:
            break
        parent = parent.parent

    return resolved


def display_path(workspace: Path, absolute: Path) -> str:
    try:
        return str(absolute.resolve().relative_to(workspace.resolve()))
    except ValueError:
        return str(absolute)
