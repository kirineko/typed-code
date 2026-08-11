"""Model catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from typed_code.api.auth import require_bearer
from typed_code.api.deps import get_state
from typed_code.protocol.models import ModelListResponse
from typed_code.service.app_state import AppState

router = APIRouter(tags=["models"], dependencies=[Depends(require_bearer)])


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models(
    refresh: bool = Query(default=False),
    state: AppState = Depends(get_state),
) -> ModelListResponse:
    if refresh:
        try:
            await state.catalog.refresh_cliproxy()
        except Exception:
            pass
    return state.catalog.list_models()
