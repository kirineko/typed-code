"""Bearer authentication for non-health routes."""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from typed_code.api.errors import structured_error_response
from typed_code.protocol.errors import ErrorCode
from typed_code.service.app_state import AppState

_bearer = HTTPBearer(auto_error=False)


async def require_bearer(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    state: AppState = request.app.state.app_state
    expected = state.credentials.server_token
    if expected is None:
        raise HTTPExceptionWithStructuredError(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="missing or invalid bearer token",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPExceptionWithStructuredError(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="missing or invalid bearer token",
        )
    if credentials.credentials != expected.get_secret_value():
        raise HTTPExceptionWithStructuredError(
            status_code=401,
            code=ErrorCode.UNAUTHORIZED,
            message="missing or invalid bearer token",
        )


class HTTPExceptionWithStructuredError(Exception):
    def __init__(self, status_code: int, code: ErrorCode, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


async def structured_http_exception_handler(
    _request: Request, exc: Exception
):
    assert isinstance(exc, HTTPExceptionWithStructuredError)
    return structured_error_response(exc.status_code, exc.code, exc.message)
