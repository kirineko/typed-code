"""Public tool lifecycle transitions."""

from __future__ import annotations

from datetime import UTC, datetime

from typed_code.domain import finish_tool, record_tool_started, start_turn
from typed_code.domain.transitions import create_session
from typed_code.protocol.common import EventType, ProviderName, ToolCallStatus
from typed_code.protocol.events import ToolStartedData
from typed_code.protocol.transcript import ToolCallItem, ToolResultItem

FIXED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _running():
    created = create_session(
        workspace_path="/tmp/ws",
        provider=ProviderName.CLIPROXY,
        model="gpt-5.6-terra",
        clock=lambda: FIXED,
        session_id="session-1",
    ).session
    return start_turn(created, "search please", clock=lambda: FIXED, run_id="run-1").session


def test_record_tool_started_is_ephemeral() -> None:
    session = _running()
    started = record_tool_started(
        session,
        tool_call_id="ws_1",
        tool_name="web_search",
        summary="search typed-code",
        clock=lambda: FIXED,
    )
    assert started.session.transcript == session.transcript
    assert started.events[0].type is EventType.TOOL_STARTED
    assert isinstance(started.events[0].data, ToolStartedData)
    assert started.events[0].data.tool_call_id == "ws_1"


def test_finish_tool_commits_call_and_result() -> None:
    session = record_tool_started(
        _running(),
        tool_call_id="ws_1",
        tool_name="web_search",
        summary="search typed-code",
        clock=lambda: FIXED,
    ).session
    finished = finish_tool(
        session,
        tool_call_id="ws_1",
        tool_name="web_search",
        summary="search completed",
        ok=True,
        call_summary="search typed-code",
        clock=lambda: FIXED,
    )
    assert finished.events[0].type is EventType.TOOL_COMPLETED
    call, result = finished.session.transcript[-2:]
    assert isinstance(call, ToolCallItem)
    assert call.id == "ws_1"
    assert call.tool_name == "web_search"
    assert call.summary == "search typed-code"
    assert call.status is ToolCallStatus.COMPLETED
    assert isinstance(result, ToolResultItem)
    assert result.tool_call_id == "ws_1"
    assert result.ok is True
    assert result.summary == "search completed"
