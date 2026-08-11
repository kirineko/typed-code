"""Live event fan-out continuity tests."""

from __future__ import annotations

from typed_code.protocol.common import EventType
from typed_code.protocol.events import EventEnvelope, RunStartedData
from typed_code.service.event_bus import EventBus


def _event(sequence: int) -> EventEnvelope:
    return EventEnvelope(
        sequence=sequence,
        timestamp="2026-08-11T00:00:00Z",
        session_id="session-1",
        run_id="run-1",
        type=EventType.RUN_STARTED,
        data=RunStartedData(run_id="run-1", prompt_preview="test"),
    )


async def test_queue_overflow_forces_reconnect_without_later_overwrite() -> None:
    bus = EventBus(maxsize=1)

    async with bus.subscribe("session-1") as queue:
        await bus.publish("session-1", [_event(1)])
        await bus.publish("session-1", [_event(2)])
        await bus.publish("session-1", [_event(3)])

        assert await queue.get() is None
        assert queue.empty()
