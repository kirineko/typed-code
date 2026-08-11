"""Per-workspace mutation coordination."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path


class WorkspaceGate:
    """Serialize mutations per workspace; reads may run concurrently."""

    def __init__(self) -> None:
        self._mutate = asyncio.Lock()
        self._read_count = 0
        self._read_lock = asyncio.Lock()

    @asynccontextmanager
    async def reading(self) -> AsyncIterator[None]:
        # Reads do not take the mutation lock; they only track concurrency for tests.
        async with self._read_lock:
            self._read_count += 1
        try:
            yield
        finally:
            async with self._read_lock:
                self._read_count -= 1

    @asynccontextmanager
    async def mutating(self) -> AsyncIterator[None]:
        async with self._mutate:
            yield

    @property
    def active_readers(self) -> int:
        return self._read_count


class WorkspaceGateRegistry:
    def __init__(self) -> None:
        self._gates: dict[str, WorkspaceGate] = {}
        self._lock = asyncio.Lock()

    async def gate_for(self, workspace: Path) -> WorkspaceGate:
        key = str(workspace.resolve())
        async with self._lock:
            gate = self._gates.get(key)
            if gate is None:
                gate = WorkspaceGate()
                self._gates[key] = gate
            return gate
