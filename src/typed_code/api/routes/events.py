"""SSE event stream routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from typed_code.api.auth import require_bearer
from typed_code.api.deps import get_state
from typed_code.domain.clock import isoformat, utc_now
from typed_code.protocol.common import EventType
from typed_code.protocol.events import EventEnvelope, ReplayResetData
from typed_code.service.app_state import AppState

router = APIRouter(tags=["events"], dependencies=[Depends(require_bearer)])

KEEPALIVE_SECONDS = 15.0


@router.get("/v1/sessions/{session_id}/events")
async def stream_events(
    session_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    state: AppState = Depends(get_state),
) -> StreamingResponse:
    # Ensure session exists
    await state.repository.get_snapshot(session_id)

    async def event_generator() -> AsyncIterator[str]:
        try:
            # Subscribe before reading persisted replay. Events committed during the
            # replay query are then either returned by the query, queued live, or both.
            async with state.event_bus.subscribe(session_id) as queue:
                replay = await state.repository.list_events(session_id, after=after)
                if replay.status == "reset":
                    assert replay.snapshot is not None
                    reset = EventEnvelope(
                        sequence=max(1, replay.snapshot.latest_event_sequence or 1),
                        timestamp=isoformat(utc_now()),
                        session_id=session_id,
                        run_id=None,
                        type=EventType.REPLAY_RESET,
                        data=ReplayResetData(snapshot=replay.snapshot),
                    )
                    yield _format_sse(reset)
                    return

                last_seq = after
                for event in replay.events:
                    if await request.is_disconnected():
                        return
                    yield _format_sse(event)
                    last_seq = event.sequence

                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                    except TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    if item is None:
                        return
                    if item.sequence <= last_seq:
                        continue
                    if item.sequence != last_seq + 1:
                        # Reconnect from last_seq so durable replay fills the gap.
                        return
                    yield _format_sse(item)
                    last_seq = item.sequence
        finally:
            state.note_authenticated_activity()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event: EventEnvelope) -> str:
    payload = event.model_dump(mode="json")
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event.sequence}\nevent: {event.type.value}\ndata: {data}\n\n"
