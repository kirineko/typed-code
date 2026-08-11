"""Secret-safe configuration errors."""

from __future__ import annotations


class ConfigurationError(Exception):
    """Raised when local configuration or credentials cannot be loaded safely.

    Messages MUST NOT include secret values, authorization headers, or full
    credential file contents.
    """

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
