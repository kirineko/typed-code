"""Workspace-scoped filesystem and Bash execution."""

from __future__ import annotations

from typed_code.workspace.backend import ExecutionBackend, LocalBashExecutionBackend
from typed_code.workspace.errors import (
    BashUnavailableError,
    EditConflictError,
    EncodingError,
    PathEscapeError,
    WorkspaceError,
)
from typed_code.workspace.locks import WorkspaceGate, WorkspaceGateRegistry
from typed_code.workspace.paths import normalize_workspace_root, resolve_in_workspace

__all__ = [
    "BashUnavailableError",
    "EditConflictError",
    "EncodingError",
    "ExecutionBackend",
    "LocalBashExecutionBackend",
    "PathEscapeError",
    "WorkspaceError",
    "WorkspaceGate",
    "WorkspaceGateRegistry",
    "normalize_workspace_root",
    "resolve_in_workspace",
]
