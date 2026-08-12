"""Health and readiness."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from typed_code.api.deps import get_state
from typed_code.protocol import PROTOCOL_VERSION, HealthResponse
from typed_code.service.app_state import AppState

router = APIRouter(tags=["health"])


@router.get("/v1/health", response_model=HealthResponse)
async def health(state: AppState = Depends(get_state)) -> HealthResponse:
    lifecycle = state.lifecycle_metadata()
    return HealthResponse.model_validate(
        {
            "status": "ok",
            "protocol_version": PROTOCOL_VERSION,
            "service": {
                **lifecycle,
                "active_work": await state.active_work_summary(),
            },
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
    )
