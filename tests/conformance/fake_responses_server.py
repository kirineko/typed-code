"""In-process fake OpenAI-compatible Responses + models endpoints."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse


@dataclass
class FakeResponsesState:
    """Mutable request log for assertions."""

    paths: list[str] = field(default_factory=list)
    bodies: list[dict[str, Any]] = field(default_factory=list)
    mode: str = "text"  # text | thinking | tools | approval | error | unknown | slow | web_search
    model_ids: list[str] = field(default_factory=lambda: ["gpt-5.6-sol", "other-model"])


def create_fake_app(state: FakeResponsesState | None = None) -> FastAPI:
    if state is None:
        state = FakeResponsesState(mode=os.environ.get("TYPED_CODE_FAKE_MODE", "text"))
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
                _sse_events(state.mode, body),
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
    if mode == "approval" and "function_call_output" not in json.dumps(request_body):
        output = [
            {
                "type": "function_call",
                "id": "fc_approval_1",
                "call_id": "call_approval_1",
                "name": "bash",
                "arguments": json.dumps(
                    {"command": "printf frozen-tool-ok > frozen-tool.txt"}
                ),
            }
        ]
    if mode == "web_search":
        output = [
            {
                "type": "web_search_call",
                "id": "ws_1",
                "status": "completed",
                "action": {"type": "search", "query": "latest typed-code release"},
            },
            {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
                "status": "completed",
            },
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


async def _sse_events(mode: str, request_body: dict[str, Any]):
    payload = _non_stream_body(mode, request_body)
    output = payload["output"]
    sequence = 1

    for output_index, item in enumerate(output):
        added_item = dict(item)
        if item["type"] == "message":
            added_item["content"] = []
            added_item["status"] = "in_progress"
        yield _sse_frame(
            "response.output_item.added",
            {
                "output_index": output_index,
                "item": added_item,
                "sequence_number": sequence,
            },
        )
        sequence += 1

        if item["type"] == "web_search_call":
            for event_type in (
                "response.web_search_call.in_progress",
                "response.web_search_call.searching",
                "response.web_search_call.completed",
            ):
                yield _sse_frame(
                    event_type,
                    {
                        "item_id": item["id"],
                        "output_index": output_index,
                        "sequence_number": sequence,
                    },
                )
                sequence += 1
        elif item["type"] == "reasoning":
            yield _sse_frame(
                "response.reasoning_summary_text.delta",
                {
                    "item_id": item["id"],
                    "output_index": output_index,
                    "summary_index": 0,
                    "delta": item["summary"][0]["text"],
                    "sequence_number": sequence,
                },
            )
            sequence += 1
        elif item["type"] == "message":
            text = item["content"][0]["text"]
            yield _sse_frame(
                "response.output_text.delta",
                {
                    "item_id": item["id"],
                    "output_index": output_index,
                    "content_index": 0,
                    "delta": text,
                    "logprobs": [],
                    "sequence_number": sequence,
                },
            )
            sequence += 1

        yield _sse_frame(
            "response.output_item.done",
            {
                "output_index": output_index,
                "item": item,
                "sequence_number": sequence,
            },
        )
        sequence += 1

    yield _sse_frame(
        "response.completed",
        {"response": payload, "sequence_number": sequence},
    )
    yield "data: [DONE]\n\n"


def _sse_frame(event_type: str, data: dict[str, Any]) -> str:
    payload = {"type": event_type, **data}
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
