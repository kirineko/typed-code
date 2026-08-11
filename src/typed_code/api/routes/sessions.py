"""Session command routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from typed_code.api.auth import require_bearer
from typed_code.api.deps import get_state
from typed_code.domain.errors import DomainNotFound, DomainValidationError
from typed_code.protocol.approvals import ApprovalDecisionRequest
from typed_code.protocol.requests import (
    AbortRequest,
    CreateTurnRequest,
    UpdateSessionModelRequest,
)
from typed_code.protocol.sessions import (
    CreateSessionRequest,
    CreateSessionResponse,
    CreateTurnResponse,
    SessionListResponse,
    SessionSnapshot,
)
from typed_code.providers.settings_normalize import ModelSelectionError
from typed_code.service.app_state import AppState

router = APIRouter(tags=["sessions"], dependencies=[Depends(require_bearer)])


@router.get("/v1/sessions", response_model=SessionListResponse)
async def list_sessions(state: AppState = Depends(get_state)) -> SessionListResponse:
    sessions = await state.repository.list_sessions()
    return SessionListResponse(sessions=sessions)


@router.post("/v1/sessions", response_model=CreateSessionResponse)
async def create_session(
    body: CreateSessionRequest,
    state: AppState = Depends(get_state),
) -> CreateSessionResponse:
    workspace = Path(body.workspace_path).expanduser()
    if not workspace.exists() or not workspace.is_dir():
        raise DomainValidationError(
            f"workspace_path must be an existing directory: {body.workspace_path}"
        )

    provider = body.provider
    model = body.model
    # Refresh discovery before default resolution so cliproxy models are current.
    if state.credentials.cliproxy_api_key is not None:
        try:
            await state.catalog.refresh_cliproxy()
        except Exception:
            pass
    try:
        resolved = state.catalog.resolve(provider, model)
    except ModelSelectionError:
        raise

    result = await state.repository.create_session(
        workspace_path=str(workspace.resolve()),
        provider=resolved.provider,
        model=resolved.model_id,
    )
    return CreateSessionResponse(snapshot=result.snapshot)


@router.get("/v1/sessions/{session_id}", response_model=SessionSnapshot)
async def get_session(
    session_id: str, state: AppState = Depends(get_state)
) -> SessionSnapshot:
    return await state.repository.get_snapshot(session_id)


@router.post(
    "/v1/sessions/{session_id}/model",
    response_model=SessionSnapshot,
)
async def update_session_model(
    session_id: str,
    body: UpdateSessionModelRequest,
    state: AppState = Depends(get_state),
) -> SessionSnapshot:
    try:
        resolved = state.catalog.resolve(body.provider, body.model)
    except ModelSelectionError:
        raise
    result = await state.repository.update_session_model(
        session_id,
        provider=resolved.provider,
        model=resolved.model_id,
    )
    return result.snapshot


@router.post(
    "/v1/sessions/{session_id}/turns",
    response_model=CreateTurnResponse,
)
async def create_turn(
    session_id: str,
    body: CreateTurnRequest,
    state: AppState = Depends(get_state),
) -> CreateTurnResponse:
    # Ensure session exists
    try:
        await state.repository.load_session(session_id)
    except DomainNotFound:
        raise
    return await state.manager.submit_turn(session_id, body.prompt)


@router.post("/v1/sessions/{session_id}/abort", response_model=SessionSnapshot)
async def abort_session(
    session_id: str,
    state: AppState = Depends(get_state),
    body: AbortRequest | None = None,
) -> SessionSnapshot:
    _ = body
    result = await state.manager.abort(session_id)
    return result.snapshot


@router.post(
    "/v1/sessions/{session_id}/approvals/{approval_id}",
    response_model=SessionSnapshot,
)
async def decide_approval(
    session_id: str,
    approval_id: str,
    body: ApprovalDecisionRequest,
    state: AppState = Depends(get_state),
) -> SessionSnapshot:
    result = await state.manager.decide_approval(
        session_id, approval_id=approval_id, decision=body.decision
    )
    return result.snapshot
