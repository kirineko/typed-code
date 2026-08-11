"""Protocol model validation and serialization."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from typed_code.protocol import (
    PROTOCOL_VERSION,
    CreateSessionRequest,
    CreateTurnRequest,
    EventEnvelope,
    EventType,
    ProviderAvailability,
    ProviderName,
    SessionPhase,
    SessionSnapshot,
)
from typed_code.protocol.events import RunStartedData
from typed_code.protocol.transcript import UserMessageItem


def test_protocol_version_constant() -> None:
    assert PROTOCOL_VERSION == 1


def test_create_session_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CreateSessionRequest.model_validate(
            {
                "workspace_path": "/tmp/ws",
                "history": [{"role": "user", "content": "nope"}],
            }
        )


def test_create_turn_rejects_empty_prompt() -> None:
    with pytest.raises(ValidationError):
        CreateTurnRequest.model_validate({"prompt": "   "})


def test_create_turn_strips_prompt() -> None:
    req = CreateTurnRequest.model_validate({"prompt": "  hello  "})
    assert req.prompt == "hello"


def test_session_snapshot_round_trip() -> None:
    snap = SessionSnapshot(
        session_id="s1",
        revision=1,
        phase=SessionPhase.IDLE,
        workspace_path="/tmp/ws",
        provider=ProviderName.CLIPROXY,
        model="gpt-5.6-sol",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        latest_event_sequence=0,
        transcript=[
            UserMessageItem(id="m1", created_at="2026-01-01T00:00:00Z", text="hi"),
        ],
    )
    restored = SessionSnapshot.model_validate_json(snap.model_dump_json())
    assert restored.session_id == "s1"
    assert restored.transcript[0].type == "user_message"
    assert restored.protocol_version == 1


def test_event_envelope_discriminator() -> None:
    env = EventEnvelope(
        sequence=1,
        timestamp="2026-01-01T00:00:00Z",
        session_id="s1",
        run_id="r1",
        type=EventType.RUN_STARTED,
        data=RunStartedData(run_id="r1", prompt_preview="hello"),
    )
    restored = EventEnvelope.model_validate_json(env.model_dump_json())
    assert restored.type == EventType.RUN_STARTED
    assert restored.data.type == EventType.RUN_STARTED
    assert restored.data.run_id == "r1"


def test_model_info_has_no_credential_fields() -> None:
    from typed_code.protocol.models import ModelInfo

    info = ModelInfo(
        provider=ProviderName.DEEPSEEK,
        model_id="deepseek-v4-flash",
        availability=ProviderAvailability.MISSING_CREDENTIALS,
    )
    payload = info.model_dump()
    assert "api_key" not in payload
    assert "token" not in payload
