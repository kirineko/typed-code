"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from typed_code.service.app_state import AppState


def get_state(request: Request) -> AppState:
    return request.app.state.app_state
