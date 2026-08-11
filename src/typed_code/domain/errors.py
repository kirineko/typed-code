"""Domain-layer errors (not yet transport-shaped)."""

from __future__ import annotations

from typed_code.protocol.errors import ErrorCode


class DomainError(Exception):
    def __init__(self, code: ErrorCode, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DomainConflict(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.CONFLICT, message)


class DomainNotFound(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.NOT_FOUND, message)


class DomainValidationError(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(ErrorCode.VALIDATION_ERROR, message)
