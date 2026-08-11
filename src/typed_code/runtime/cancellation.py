"""First-party cancellation scopes for active runs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class RunCancelScope:
    """Per-run cancel flag + optional asyncio task handle."""

    _event: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[object] | None = None

    def request_cancel(self) -> None:
        self._event.set()
        if self.task is not None and not self.task.done():
            self.task.cancel()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def reset(self) -> None:
        self._event = asyncio.Event()
        self.task = None
