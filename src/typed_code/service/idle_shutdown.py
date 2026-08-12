"""Optional idle-shutdown policy with active-work suppression."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

ActiveWorkProbe = Callable[[], Awaitable[dict[str, int]]]


@dataclass
class IdleShutdownMonitor:
    """Wait until inactivity exceeds the configured timeout with no blockers."""

    timeout_seconds: float | None = None
    blocker_poll_seconds: float = 1.0
    _last_activity: float = field(default_factory=time.monotonic)
    _changed: asyncio.Event = field(default_factory=asyncio.Event)

    def configure(self, timeout_seconds: float | None) -> None:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("idle timeout must be positive or disabled")
        self.timeout_seconds = timeout_seconds
        self.note_activity()

    def note_activity(self) -> None:
        self._last_activity = time.monotonic()
        self._changed.set()

    async def wait_for_shutdown(self, active_work: ActiveWorkProbe) -> None:
        while True:
            timeout = self.timeout_seconds
            if timeout is None:
                await self._wait_for_change(None)
                continue

            remaining = timeout - (time.monotonic() - self._last_activity)
            if remaining > 0:
                await self._wait_for_change(remaining)
                continue

            summary = await active_work()
            if all(count == 0 for count in summary.values()):
                return
            await self._wait_for_change(self.blocker_poll_seconds)

    async def _wait_for_change(self, timeout: float | None) -> None:
        self._changed.clear()
        if timeout is None:
            await self._changed.wait()
            return
        try:
            await asyncio.wait_for(self._changed.wait(), timeout=timeout)
        except TimeoutError:
            pass
