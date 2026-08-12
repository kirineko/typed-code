"""Authenticated lifecycle administration for the local singleton service."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from typed_code.api.auth import require_bearer
from typed_code.api.deps import get_state
from typed_code.protocol import ServiceStopRequest, ServiceStopResponse
from typed_code.service.app_state import AppState

router = APIRouter(tags=["service"], dependencies=[Depends(require_bearer)])


@router.post("/v1/service/stop", response_model=ServiceStopResponse)
async def stop_service(
    body: ServiceStopRequest,
    state: AppState = Depends(get_state),
) -> ServiceStopResponse:
    interrupted = await state.request_shutdown(force=body.force)
    return ServiceStopResponse(forced=body.force, interrupted_runs=interrupted)
