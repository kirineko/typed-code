"""Contract artifact checks."""

from __future__ import annotations

import json
from pathlib import Path

from typed_code.api.export_contracts import export_contracts
from typed_code.protocol.common import EventType


def test_export_contracts(tmp_path: Path) -> None:
    export_contracts(tmp_path)
    openapi = json.loads((tmp_path / "openapi.v1.json").read_text(encoding="utf-8"))
    assert "/v1/health" in openapi["paths"]
    assert "/v1/sessions" in openapi["paths"]
    assert "/v1/sessions/{session_id}/events" in openapi["paths"]
    blob = json.dumps(openapi)
    assert "pydantic_ai" not in blob
    assert "openai" not in blob.lower() or "OpenAPI" in blob

    events = json.loads((tmp_path / "events.schema.v1.json").read_text(encoding="utf-8"))
    assert "properties" in events or "$defs" in events or "anyOf" in events
    # Event types present somewhere in schema text
    text = json.dumps(events)
    assert EventType.RUN_STARTED.value in text or "run.started" in text
