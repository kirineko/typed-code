"""Owns at most one active asyncio run task per session."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from typed_code.domain.errors import DomainConflict
from typed_code.persistence.repository import PersistResult, SessionRepository
from typed_code.protocol.common import ApprovalDecision, SessionPhase
from typed_code.protocol.sessions import CreateTurnResponse
from typed_code.providers.settings_normalize import RunSettingRequest
from typed_code.runtime.adapter import AgentRuntime
from typed_code.service.event_bus import EventBus


@dataclass
class SessionManager:
    repository: SessionRepository  # may be PublishingRepository duck-type
    runtime: AgentRuntime
    event_bus: EventBus
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def recover(self) -> list[PersistResult]:
        return await self.repository.recover_abandoned_runs()

    async def submit_turn(
        self,
        session_id: str,
        prompt: str,
        *,
        setting_request: RunSettingRequest | None = None,
    ) -> CreateTurnResponse:
        async with self._lock:
            session = await self.repository.load_session(session_id)
            if session.phase is not SessionPhase.IDLE:
                raise DomainConflict("session already has an active run")
            existing = self._tasks.get(session_id)
            if existing is not None and not existing.done():
                raise DomainConflict("session already has an active run")

            started = asyncio.Event()
            error_box: list[BaseException] = []

            async def runner() -> None:
                try:
                    # Signal once start_turn has been entered via first durable change
                    # by polling after kickoff; runtime.start is internal.
                    await self.runtime.run_turn(
                        session_id, prompt, setting_request=setting_request
                    )
                except BaseException as exc:
                    error_box.append(exc)
                    raise
                finally:
                    started.set()
                    async with self._lock:
                        if self._tasks.get(session_id) is asyncio.current_task():
                            self._tasks.pop(session_id, None)

            task = asyncio.create_task(runner(), name=f"typed-code-turn-{session_id}")
            self._tasks[session_id] = task

        # Wait until session leaves idle or task fails.
        for _ in range(200):
            if task.done():
                if error_box:
                    raise error_box[0]
                exc = task.exception()
                if exc is not None:
                    raise exc
                break
            snap = await self.repository.get_snapshot(session_id)
            if snap.phase is not SessionPhase.IDLE:
                run_id = snap.active_run.run_id if snap.active_run else ""
                return CreateTurnResponse(
                    run_id=run_id or "pending",
                    revision=snap.revision,
                    phase=snap.phase,
                )
            await asyncio.sleep(0.01)

        snap = await self.repository.get_snapshot(session_id)
        run_id = snap.active_run.run_id if snap.active_run else ""
        return CreateTurnResponse(
            run_id=run_id or "unknown",
            revision=snap.revision,
            phase=snap.phase,
        )

    async def abort(self, session_id: str) -> PersistResult:
        """Cancel the durable run and best-effort stop the in-process task.

        The HTTP response MUST return after durable cancel is committed. Waiting
        indefinitely for a stuck provider stream would hang abort clients.
        """
        result = await self.runtime.cancel(session_id)
        async with self._lock:
            task = self._tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
            except (TimeoutError, asyncio.CancelledError, Exception):
                # Task may still be draining a provider stream; durable state is
                # already cancelled. A late task must tolerate DomainConflict.
                pass
        return result

    async def decide_approval(
        self,
        session_id: str,
        *,
        approval_id: str,
        decision: ApprovalDecision,
    ) -> PersistResult:
        async with self._lock:
            existing = self._tasks.get(session_id)
            if existing is not None and not existing.done():
                raise DomainConflict("session run task is still active")

            async def runner() -> None:
                try:
                    await self.runtime.resume_after_approval(
                        session_id, approval_id=approval_id, decision=decision
                    )
                finally:
                    async with self._lock:
                        if self._tasks.get(session_id) is asyncio.current_task():
                            self._tasks.pop(session_id, None)

            task = asyncio.create_task(
                runner(), name=f"typed-code-resume-{session_id}"
            )
            self._tasks[session_id] = task

        # Wait for approval to be applied at least (phase may leave awaiting or complete)
        for _ in range(200):
            if task.done():
                exc = task.exception()
                if exc is not None:
                    raise exc
                break
            snap = await self.repository.get_snapshot(session_id)
            # Decision applied when approval no longer pending
            pending_ids = {a.approval_id for a in snap.pending_approvals}
            if approval_id not in pending_ids:
                break
            await asyncio.sleep(0.01)

        return PersistResult(
            snapshot=await self.repository.get_snapshot(session_id),
            events=[],
        )

    def has_active_task(self, session_id: str) -> bool:
        task = self._tasks.get(session_id)
        return task is not None and not task.done()
