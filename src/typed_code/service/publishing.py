"""Repository proxy that publishes PersistResult events after commit."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from typed_code.persistence.repository import PersistResult, SessionRepository
from typed_code.protocol.events import EventEnvelope

PublishHook = Callable[[str, list[EventEnvelope]], Awaitable[None]]


class PublishingRepository(SessionRepository):  # type: ignore[misc]
    """Delegates to SessionRepository and publishes committed public events.

    Subclasses for typing only; methods do not call super().
    """

    def __init__(self, inner: SessionRepository, publish: PublishHook) -> None:
        # Do not call SessionRepository.__init__; we wrap an existing instance.
        self._inner = inner
        self._publish = publish
        self._db = inner._db
        self._event_retention_count = inner._event_retention_count

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    async def _emit(self, result: PersistResult) -> PersistResult:
        if result.events:
            await self._publish(result.snapshot.session_id, list(result.events))
        return result

    async def create_session(self, **kwargs: Any) -> PersistResult:
        return await self._emit(await self._inner.create_session(**kwargs))

    async def start_turn(self, session_id: str, prompt: str) -> PersistResult:
        return await self._emit(await self._inner.start_turn(session_id, prompt))

    async def update_session_model(self, session_id: str, **kwargs: Any) -> PersistResult:
        return await self._emit(
            await self._inner.update_session_model(session_id, **kwargs)
        )

    async def record_assistant_delta(
        self, session_id: str, **kwargs: Any
    ) -> PersistResult:
        return await self._emit(
            await self._inner.record_assistant_delta(session_id, **kwargs)
        )

    async def record_thinking_delta(
        self, session_id: str, **kwargs: Any
    ) -> PersistResult:
        return await self._emit(
            await self._inner.record_thinking_delta(session_id, **kwargs)
        )

    async def finish_thinking(
        self, session_id: str, **kwargs: Any
    ) -> PersistResult:
        return await self._emit(
            await self._inner.finish_thinking(session_id, **kwargs)
        )

    async def complete_run(self, session_id: str) -> PersistResult:
        return await self._emit(await self._inner.complete_run(session_id))

    async def fail_run(self, session_id: str, error: Any) -> PersistResult:
        return await self._emit(await self._inner.fail_run(session_id, error))

    async def cancel_run(self, session_id: str) -> PersistResult:
        return await self._emit(await self._inner.cancel_run(session_id))

    async def interrupt_run(self, session_id: str) -> PersistResult:
        return await self._emit(await self._inner.interrupt_run(session_id))

    async def request_approval(self, session_id: str, **kwargs: Any) -> PersistResult:
        return await self._emit(await self._inner.request_approval(session_id, **kwargs))

    async def resolve_approval(self, session_id: str, **kwargs: Any) -> PersistResult:
        return await self._emit(await self._inner.resolve_approval(session_id, **kwargs))

    async def finish_assistant_turn(self, session_id: str, **kwargs: Any) -> PersistResult:
        return await self._emit(
            await self._inner.finish_assistant_turn(session_id, **kwargs)
        )

    async def record_compaction_event(self, session_id: str, **kwargs: Any) -> PersistResult:
        return await self._emit(
            await self._inner.record_compaction_event(session_id, **kwargs)
        )

    async def recover_abandoned_runs(self) -> list[PersistResult]:
        results = await self._inner.recover_abandoned_runs()
        for result in results:
            await self._emit(result)
        return results
