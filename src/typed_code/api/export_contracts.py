"""Export OpenAPI and SSE event schema contract artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI

from typed_code.api.routes import config, events, health, models, service, sessions
from typed_code.protocol.events import EventEnvelope


def build_export_app() -> FastAPI:
    """App shell for OpenAPI generation without loading credentials."""
    app = FastAPI(
        title="typed-code",
        version="0.1.0",
        description="Server-authoritative coding agent service (Responses API)",
    )
    app.include_router(health.router)
    app.include_router(models.router)
    app.include_router(config.router)
    app.include_router(service.router)
    app.include_router(sessions.router)
    app.include_router(events.router)
    return app


def export_contracts(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    app = build_export_app()
    openapi = app.openapi()
    text = json.dumps(openapi, indent=2, ensure_ascii=False) + "\n"
    (out_dir / "openapi.v1.json").write_text(text, encoding="utf-8")

    event_schema = EventEnvelope.model_json_schema()
    (out_dir / "events.schema.v1.json").write_text(
        json.dumps(event_schema, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    export_contracts(root / "contracts")
    print("wrote contracts/openapi.v1.json and contracts/events.schema.v1.json")


if __name__ == "__main__":
    main()
