"""Mutation lock coordination."""

from __future__ import annotations

import asyncio

import pytest

from typed_code.workspace.locks import WorkspaceGate


@pytest.mark.asyncio
async def test_mutations_serialize() -> None:
    gate = WorkspaceGate()
    order: list[str] = []

    async def mut(name: str) -> None:
        async with gate.mutating():
            order.append(f"start-{name}")
            await asyncio.sleep(0.05)
            order.append(f"end-{name}")

    await asyncio.gather(mut("a"), mut("b"))
    # No interleaving of start/end pairs
    assert order in (
        ["start-a", "end-a", "start-b", "end-b"],
        ["start-b", "end-b", "start-a", "end-a"],
    )


@pytest.mark.asyncio
async def test_parallel_reads() -> None:
    gate = WorkspaceGate()

    async def reader() -> int:
        async with gate.reading():
            await asyncio.sleep(0.05)
            return gate.active_readers

    counts = await asyncio.gather(reader(), reader(), reader())
    assert max(counts) >= 2
