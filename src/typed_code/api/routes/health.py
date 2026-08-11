"""Health and readiness."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from typed_code.api.deps import get_state
from typed_code.protocol import PROTOCOL_VERSION
from typed_code.service.app_state import AppState

router = APIRouter(tags=["health"])


@router.get("/v1/health")
async def health(state: AppState = Depends(get_state)) -> dict[str, Any]:
    return {
        "status": "ok",
        "protocol_version": PROTOCOL_VERSION,
        "providers": {
            "deepseek": state.credentials.deepseek_availability.value,
            "cliproxy": state.credentials.cliproxy_availability.value,
        },
        "bash": {
            "ready": state.bash_ready,
            "executable": state.bash_executable,
        },
        "default_provider": state.settings.default_provider,
        "default_model": state.settings.default_model,
    }
