"""Per-session live event fan-out for SSE observers."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from typed_code.protocol.events import EventEnvelope


@dataclass
class _Subscriber:
    queue: asyncio.Queue[EventEnvelope | None]
    overflowed: bool = False



@dataclass
class EventBus:
    """In-process pub/sub of committed public events."""

    maxsize: int = 256
    _subs: dict[str, list[_Subscriber]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def publish(self, session_id: str, events: list[EventEnvelope]) -> None:
        if not events:
            return
        async with self._lock:
            subscribers = list(self._subs.get(session_id, ()))
        for event in events:
            for subscriber in subscribers:
                if subscriber.overflowed:
                    continue
                try:
                    subscriber.queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Force a reconnect instead of silently creating a sequence gap.
                    subscriber.overflowed = True
                    while not subscriber.queue.empty():
                        subscriber.queue.get_nowait()
                    subscriber.queue.put_nowait(None)

    @asynccontextmanager
    async def subscribe(
        self, session_id: str
    ) -> AsyncIterator[asyncio.Queue[EventEnvelope | None]]:
        subscriber = _Subscriber(
            queue=asyncio.Queue(maxsize=self.maxsize)
        )
        async with self._lock:
            self._subs[session_id].append(subscriber)
        try:
            yield subscriber.queue
        finally:
            async with self._lock:
                subscribers = self._subs.get(session_id, [])
                if subscriber in subscribers:
                    subscribers.remove(subscriber)
                if not subscribers and session_id in self._subs:
                    del self._subs[session_id]
