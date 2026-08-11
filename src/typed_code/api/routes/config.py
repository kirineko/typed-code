"""Authenticated configuration reload."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from typed_code.api.auth import require_bearer
from typed_code.api.deps import get_state
from typed_code.config.errors import ConfigurationError
from typed_code.service.app_state import AppState

router = APIRouter(tags=["config"], dependencies=[Depends(require_bearer)])


class ConfigReloadResponse(BaseModel):
    reloaded: bool = True
    providers: dict[str, str] = Field(default_factory=dict)


@router.post("/v1/config/reload", response_model=ConfigReloadResponse)
async def reload_config(state: AppState = Depends(get_state)) -> ConfigReloadResponse:
    try:
        providers = await state.reload_configuration()
    except ConfigurationError:
        raise
    return ConfigReloadResponse(reloaded=True, providers=providers)
