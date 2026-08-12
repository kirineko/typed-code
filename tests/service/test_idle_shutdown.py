"""Idle shutdown remains opt-in and is suppressed by active work."""

from __future__ import annotations

import asyncio

from typed_code.service.idle_shutdown import IdleShutdownMonitor


async def test_idle_shutdown_is_disabled_by_default_and_activity_resets_clock() -> None:
    monitor = IdleShutdownMonitor(blocker_poll_seconds=0.005)

    task = asyncio.create_task(monitor.wait_for_shutdown(lambda: _summary()))
    await asyncio.sleep(0.02)
    assert not task.done()

    monitor.configure(0.03)
    await asyncio.sleep(0.02)
    monitor.note_activity()
    await asyncio.sleep(0.02)
    assert not task.done()

    await asyncio.wait_for(task, timeout=0.1)


async def test_active_runs_approvals_and_streams_each_suppress_idle_exit() -> None:
    state = {
        "active_runs": 1,
        "pending_approvals": 1,
        "connected_event_streams": 1,
    }
    monitor = IdleShutdownMonitor(
        timeout_seconds=0.01,
        blocker_poll_seconds=0.005,
    )

    async def active_work() -> dict[str, int]:
        return dict(state)

    task = asyncio.create_task(monitor.wait_for_shutdown(active_work))
    await asyncio.sleep(0.03)
    assert not task.done()

    state["active_runs"] = 0
    await asyncio.sleep(0.02)
    assert not task.done()
    state["pending_approvals"] = 0
    await asyncio.sleep(0.02)
    assert not task.done()
    state["connected_event_streams"] = 0

    await asyncio.wait_for(task, timeout=0.1)


async def _summary() -> dict[str, int]:
    return {
        "active_runs": 0,
        "pending_approvals": 0,
        "connected_event_streams": 0,
    }
