"""In-process fake OpenAI-compatible Responses + models endpoints."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse


@dataclass
class FakeResponsesState:
    """Mutable request log for assertions."""

    paths: list[str] = field(default_factory=list)
    bodies: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "text"  # text | thinking | tools | error | unknown | slow
    model_ids: list[str] = field(default_factory=lambda: ["gpt-5.6-sol", "other-model"])


def create_fake_app(state: FakeResponsesState | None = None) -> FastAPI:
    state = state or FakeResponsesState()
    app = FastAPI()

    @app.middleware("http")
    async def log_paths(request: Request, call_next):  # type: ignore[no-untyped-def]
        state.paths.append(request.url.path)
        return await call_next(request)

    @app.get("/v1/models")
    @app.get("/models")
    async def list_models() -> dict[str, Any]:
        return {
            "object": "list",
            "data": [{"id": mid, "object": "model"} for mid in state.model_ids],
        }

    @app.post("/v1/responses")
    @app.post("/responses")
    async def create_response(request: Request) -> Response:
        body = await request.json()
        state.bodies.append(body)
        if state.mode == "error":
            return JSONResponse(
                status_code=500,
                content={"error": {"message": "upstream failure", "type": "server_error"}},
            )

        stream = bool(body.get("stream"))
        if stream:
            return StreamingResponse(
                _sse_events(state.mode),
                media_type="text/event-stream",
            )
        return JSONResponse(_non_stream_body(state.mode, body))

    @app.post("/v1/chat/completions")
    @app.post("/chat/completions")
    async def chat_completions() -> JSONResponse:
        # Should never be hit by Responses-only runtime
        state.paths.append("/v1/chat/completions-HIT")
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "chat completions disabled in fake"}},
        )

    app.state.fake = state  # type: ignore[attr-defined]
    return app


def _non_stream_body(mode: str, request_body: dict[str, Any]) -> dict[str, Any]:
    model = request_body.get("model", "fake-model")
    text = "hello from fake responses"
    output: list[dict[str, Any]] = [
        {
            "type": "message",
            "id": "msg_1",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text}],
            "status": "completed",
        }
    ]
    if mode == "thinking":
        output.insert(
            0,
            {
                "type": "reasoning",
                "id": "rsn_1",
                "summary": [{"type": "summary_text", "text": "thinking..."}],
            },
        )
    if mode == "tools":
        output = [
            {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": "echo",
                "arguments": json.dumps({"text": "hi"}),
            }
        ]
    if mode == "unknown":
        output.append({"type": "typed_code_unknown_event", "id": "unk_1", "payload": {}})

    return {
        "id": "resp_fake_1",
        "object": "response",
        "created_at": 1_700_000_000,
        "status": "completed",
        "model": model,
        "output": output,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        },
    }


async def _sse_events(mode: str):
    # Minimal SSE frames; OpenAI client is resilient enough for basic cases.
    # Prefer non-stream in most tests; this path exists for coverage.
    payload = _non_stream_body(mode, {"model": "fake"})
    yield f"event: response.completed\ndata: {json.dumps(payload)}\n\n"
    yield "data: [DONE]\n\n"
