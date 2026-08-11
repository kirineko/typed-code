"""Map domain/config errors to HTTP StructuredError responses."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from typed_code.config.errors import ConfigurationError
from typed_code.domain.errors import DomainConflict, DomainError, DomainNotFound
from typed_code.protocol.errors import ErrorCode, ErrorResponse, StructuredError
from typed_code.providers.settings_normalize import ModelSelectionError


def structured_error_response(
    status_code: int, code: ErrorCode, message: str, details: dict | None = None
) -> JSONResponse:
    body = ErrorResponse(
        error=StructuredError(code=code, message=message, details=details)
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    status = 400
    if isinstance(exc, DomainNotFound):
        status = 404
    elif isinstance(exc, DomainConflict):
        status = 409
    elif isinstance(exc, ModelSelectionError):
        status = 400
    return structured_error_response(status, exc.code, exc.message)


async def configuration_error_handler(
    _request: Request, exc: ConfigurationError
) -> JSONResponse:
    code = ErrorCode.CONFIGURATION_ERROR
    if exc.code == "missing_server_token":
        code = ErrorCode.CONFIGURATION_ERROR
    return structured_error_response(500, code, exc.message)


async def validation_error_handler(
    _request: Request, exc: ValidationError
) -> JSONResponse:
    return structured_error_response(
        422,
        ErrorCode.VALIDATION_ERROR,
        "request validation failed",
        details={"errors": exc.errors()},
    )
