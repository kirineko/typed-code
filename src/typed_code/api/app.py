"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI
from pydantic import ValidationError

from typed_code.api.auth import (
    HTTPExceptionWithStructuredError,
    structured_http_exception_handler,
)
from typed_code.api.errors import (
    configuration_error_handler,
    domain_error_handler,
    validation_error_handler,
)
from typed_code.api.routes import config, events, health, models, sessions
from typed_code.config.errors import ConfigurationError
from typed_code.domain.errors import DomainError
from typed_code.service.app_state import AppState, build_app_state


def create_app(state: AppState | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if state is None:
            app.state.app_state = await build_app_state()
            owns = True
        else:
            app.state.app_state = state
            owns = False
        try:
            yield
        finally:
            if owns:
                await app.state.app_state.aclose()

    app = FastAPI(
        title="typed-code",
        version="0.1.0",
        description="Server-authoritative coding agent service (Responses API)",
        lifespan=lifespan,
    )
    if state is not None:
        app.state.app_state = state

    # Starlette's ExceptionHandler union is overly strict for typed handlers.
    app.add_exception_handler(DomainError, cast(Any, domain_error_handler))
    app.add_exception_handler(ConfigurationError, cast(Any, configuration_error_handler))
    app.add_exception_handler(ValidationError, cast(Any, validation_error_handler))
    app.add_exception_handler(
        HTTPExceptionWithStructuredError,
        cast(Any, structured_http_exception_handler),
    )

    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(config.router)
    app.include_router(sessions.router)
    app.include_router(events.router)
    return app
