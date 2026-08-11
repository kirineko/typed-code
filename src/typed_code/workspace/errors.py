"""Workspace execution errors (not transport-shaped)."""

from __future__ import annotations


class WorkspaceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class PathEscapeError(WorkspaceError):
    def __init__(self, message: str) -> None:
        super().__init__("path_escape", message)


class EncodingError(WorkspaceError):
    def __init__(self, message: str) -> None:
        super().__init__("encoding_error", message)


class EditConflictError(WorkspaceError):
    def __init__(self, message: str) -> None:
        super().__init__("edit_conflict", message)


class BashUnavailableError(WorkspaceError):
    def __init__(self, message: str) -> None:
        super().__init__("bash_unavailable", message)


class FileNotFoundWorkspaceError(WorkspaceError):
    def __init__(self, message: str) -> None:
        super().__init__("file_not_found", message)
