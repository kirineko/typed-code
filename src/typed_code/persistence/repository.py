"""Session repository: atomic domain transitions + public events."""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import wraps
from typing import Any, Concatenate, Literal, cast

import aiosqlite

from typed_code.compaction.compact import ModelMessageRecord
from typed_code.domain.errors import DomainNotFound
from typed_code.domain.ids import new_id, new_message_id
from typed_code.domain.session import (
    ApprovalState,
    ContextUsageCheckpoint,
    RunState,
    SessionState,
)
from typed_code.domain.transitions import (
    TransitionResult,
    cancel_run,
    complete_run,
    create_session,
    fail_run,
    finish_assistant_turn,
    finish_thinking,
    interrupt_run,
    record_assistant_delta,
    record_compaction,
    record_thinking_delta,
    request_approval,
    resolve_approval,
    start_turn,
    update_session_model,
)
from typed_code.persistence.db import Database
from typed_code.persistence.mapping import (
    event_data_to_json,
    event_type_value,
    parse_event_envelope,
    parse_transcript_item,
    row_approval,
    row_run,
    row_session_core,
    session_to_snapshot,
    transcript_item_to_json,
)
from typed_code.protocol.common import (
    TERMINAL_RUN_STATUSES,
    ApprovalDecision,
    ApprovalStatus,
    ProviderName,
)
from typed_code.protocol.errors import StructuredError
from typed_code.protocol.events import EventEnvelope
from typed_code.protocol.sessions import SessionSnapshot, SessionSummary
from typed_code.protocol.transcript import TranscriptItem


def _serialized_operation[**P, R](
    method: Callable[Concatenate[SessionRepository, P], Coroutine[Any, Any, R]],
) -> Callable[Concatenate[SessionRepository, P], Coroutine[Any, Any, R]]:
    """Hold the shared-connection gate for one complete repository operation."""

    @wraps(method)
    async def wrapped(
        self: SessionRepository, *args: P.args, **kwargs: P.kwargs
    ) -> R:
        async with self._db.operation():
            return await method(self, *args, **kwargs)

    return cast(
        "Callable[Concatenate[SessionRepository, P], Coroutine[Any, Any, R]]",
        wrapped,
    )


@dataclass(frozen=True)
class PersistResult:
    """Committed state ready for optional publication after the transaction."""

    snapshot: SessionSnapshot
    events: list[EventEnvelope]


@dataclass(frozen=True)
class ReplayResult:
    status: Literal["ok", "reset"]
    events: list[EventEnvelope]
    snapshot: SessionSnapshot | None


class SessionRepository:
    def __init__(self, db: Database, *, event_retention_count: int = 2000) -> None:
        if event_retention_count < 1:
            raise ValueError("event_retention_count must be >= 1")
        self._db = db
        self._event_retention_count = event_retention_count

    @property
    def connection(self) -> aiosqlite.Connection:
        return self._db.connection

    async def create_session(
        self,
        *,
        workspace_path: str,
        provider: ProviderName,
        model: str,
    ) -> PersistResult:
        result = create_session(
            workspace_path=workspace_path,
            provider=provider,
            model=model,
        )
        return await self._commit_transition(result, is_new_session=True)

    async def start_turn(self, session_id: str, prompt: str) -> PersistResult:
        return await self._mutate(session_id, lambda s: start_turn(s, prompt))

    async def update_session_model(
        self,
        session_id: str,
        *,
        provider: ProviderName,
        model: str,
    ) -> PersistResult:
        return await self._mutate(
            session_id,
            lambda s: update_session_model(s, provider=provider, model=model),
        )

    async def record_assistant_delta(
        self, session_id: str, *, message_id: str, delta: str
    ) -> PersistResult:
        return await self._mutate(
            session_id,
            lambda s: record_assistant_delta(
                s, message_id=message_id, delta=delta
            ),
        )

    async def record_thinking_delta(
        self, session_id: str, *, thinking_id: str, delta: str
    ) -> PersistResult:
        return await self._mutate(
            session_id,
            lambda s: record_thinking_delta(
                s, thinking_id=thinking_id, delta=delta
            ),
        )

    async def finish_thinking(
        self, session_id: str, *, thinking_id: str, text: str
    ) -> PersistResult:
        return await self._mutate(
            session_id,
            lambda s: finish_thinking(s, thinking_id=thinking_id, text=text),
        )

    async def complete_run(self, session_id: str) -> PersistResult:
        return await self._mutate(session_id, complete_run)

    async def fail_run(self, session_id: str, error: StructuredError) -> PersistResult:
        return await self._mutate(session_id, lambda s: fail_run(s, error=error))

    async def cancel_run(self, session_id: str) -> PersistResult:
        return await self._mutate(session_id, cancel_run)

    async def interrupt_run(self, session_id: str) -> PersistResult:
        return await self._mutate(session_id, interrupt_run)

    async def request_approval(
        self,
        session_id: str,
        *,
        tool_call_id: str,
        tool_name: str,
        summary: str,
        request_json: str,
    ) -> PersistResult:
        return await self._mutate(
            session_id,
            lambda s: request_approval(
                s,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                summary=summary,
                request_json=request_json,
            ),
        )

    async def resolve_approval(
        self,
        session_id: str,
        *,
        approval_id: str,
        decision: ApprovalDecision,
    ) -> PersistResult:
        return await self._mutate(
            session_id,
            lambda s: resolve_approval(s, approval_id=approval_id, decision=decision),
        )

    async def get_snapshot(self, session_id: str) -> SessionSnapshot:
        session = await self.load_session(session_id)
        return session_to_snapshot(session)

    @_serialized_operation
    async def list_sessions(self) -> list[SessionSummary]:
        cursor = await self.connection.execute(
            """
            SELECT id, workspace_path, provider, model, phase, active_run_id,
                   revision, latest_event_sequence, created_at, updated_at
            FROM sessions
            ORDER BY updated_at DESC
            """
        )
        rows = await cursor.fetchall()
        summaries: list[SessionSummary] = []
        for row in rows:
            core = row_session_core(row)
            summaries.append(
                SessionSummary(
                    session_id=core["session_id"],
                    revision=core["revision"],
                    phase=core["phase"],
                    workspace_path=core["workspace_path"],
                    provider=core["provider"],
                    model=core["model"],
                    created_at=core["created_at"],
                    updated_at=core["updated_at"],
                    active_run_id=core["active_run_id"],
                )
            )
        return summaries

    @_serialized_operation
    async def load_session(self, session_id: str) -> SessionState:
        cursor = await self.connection.execute(
            """
            SELECT id, workspace_path, provider, model, phase, active_run_id,
                   revision, latest_event_sequence, created_at, updated_at,
                   last_usage_tokens, last_usage_message_count
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise DomainNotFound(f"session not found: {session_id}")
        return await self._hydrate_session(row)

    @_serialized_operation
    async def list_events(self, session_id: str, *, after: int) -> ReplayResult:
        if after < 0:
            raise ValueError("after must be >= 0")

        # Ensure session exists
        session = await self.load_session(session_id)
        snapshot = session_to_snapshot(session)

        cursor = await self.connection.execute(
            """
            SELECT MIN(sequence) AS min_seq, MAX(sequence) AS max_seq
            FROM events WHERE session_id = ?
            """,
            (session_id,),
        )
        bounds = await cursor.fetchone()
        if bounds is None:
            return ReplayResult(status="ok", events=[], snapshot=None)
        min_seq = bounds["min_seq"]
        max_seq = bounds["max_seq"]

        if max_seq is None:
            # No events retained or ever written
            if after == 0:
                return ReplayResult(status="ok", events=[], snapshot=None)
            return ReplayResult(status="reset", events=[], snapshot=snapshot)

        min_seq_i = int(min_seq)
        # If after points before retained window, client must reload snapshot
        if after + 1 < min_seq_i:
            return ReplayResult(status="reset", events=[], snapshot=snapshot)

        cursor = await self.connection.execute(
            """
            SELECT session_id, sequence, run_id, type, data_json, created_at
            FROM events
            WHERE session_id = ? AND sequence > ?
            ORDER BY sequence ASC
            """,
            (session_id, after),
        )
        rows = await cursor.fetchall()
        events = [
            parse_event_envelope(
                session_id=r["session_id"],
                sequence=int(r["sequence"]),
                run_id=r["run_id"],
                type_value=r["type"],
                data_json=r["data_json"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
        return ReplayResult(status="ok", events=events, snapshot=None)

    @_serialized_operation
    async def recover_abandoned_runs(self) -> list[PersistResult]:
        """Mark all non-terminal runs interrupted (process start has no live owners)."""
        cursor = await self.connection.execute(
            f"""
            SELECT DISTINCT session_id FROM runs
            WHERE status NOT IN ({",".join("?" for _ in TERMINAL_RUN_STATUSES)})
            """,
            tuple(s.value for s in TERMINAL_RUN_STATUSES),
        )
        rows = await cursor.fetchall()
        results: list[PersistResult] = []
        for row in rows:
            session_id = row["session_id"]
            # Only interrupt if session still points at a non-terminal active run
            session = await self.load_session(session_id)
            if session.active_run is None:
                continue
            if session.active_run.status in TERMINAL_RUN_STATUSES:
                continue
            results.append(await self.interrupt_run(session_id))
        return results

    @_serialized_operation
    async def list_model_messages(self, session_id: str) -> list[ModelMessageRecord]:
        await self.load_session(session_id)  # not-found check
        cursor = await self.connection.execute(
            """
            SELECT id, session_id, run_id, position, role, payload_json, created_at
            FROM model_messages
            WHERE session_id = ?
            ORDER BY position ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [
            ModelMessageRecord(
                id=r["id"],
                session_id=r["session_id"],
                run_id=r["run_id"],
                position=int(r["position"]),
                role=r["role"],
                payload_json=r["payload_json"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    @_serialized_operation
    async def list_run_approval_decisions(
        self, session_id: str, *, run_id: str
    ) -> dict[str, bool]:
        """Map tool_call_id → approved for resolved approvals on a run."""
        cursor = await self.connection.execute(
            """
            SELECT tool_call_id, status, decision, request_json
            FROM approvals
            WHERE session_id = ? AND run_id = ? AND status IN ('approved', 'rejected')
            """,
            (session_id, run_id),
        )
        rows = await cursor.fetchall()
        out: dict[str, bool] = {}
        for row in rows:
            tool_call_id = row["tool_call_id"]
            try:
                payload = json.loads(row["request_json"] or "{}")
                if isinstance(payload.get("tool_call_id"), str):
                    tool_call_id = payload["tool_call_id"]
            except json.JSONDecodeError:
                pass
            out[tool_call_id] = row["status"] == "approved" or row["decision"] == "approve"
        return out

    async def append_model_messages(
        self, session_id: str, drafts: list[Any]
    ) -> None:
        """Append opaque model message rows without changing session phase."""
        async with self._db.write_transaction():
            await self.load_session(session_id)
            cur = await self.connection.execute(
                "SELECT COALESCE(MAX(position), 0) FROM model_messages WHERE session_id = ?",
                (session_id,),
            )
            row = await cur.fetchone()
            next_pos = int(row[0] if row is not None else 0) + 1
            from typed_code.domain.clock import isoformat, utc_now

            now = isoformat(utc_now())
            for draft in drafts:
                await self.connection.execute(
                    """
                    INSERT INTO model_messages (
                        id, session_id, run_id, position, role, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_message_id(),
                        session_id,
                        getattr(draft, "run_id", None),
                        next_pos,
                        getattr(draft, "role", "unknown"),
                        getattr(draft, "payload_json", ""),
                        now,
                    ),
                )
                next_pos += 1

    async def apply_transition(
        self, session_id: str, fn: Any, *, is_new_session: bool = False
    ) -> PersistResult:
        """Apply a pure domain transition function under a write transaction."""
        if is_new_session:
            raise ValueError("use create_session for new sessions")
        return await self._mutate(session_id, fn)

    async def finish_assistant_turn(
        self,
        session_id: str,
        *,
        assistant_text: str,
        model_message_payloads: list[Any],
        usage: dict[str, int | None] | None = None,
        message_id: str | None = None,
    ) -> PersistResult:
        async with self._db.write_transaction():
            session = await self._load_session_for_update(session_id)
            result = finish_assistant_turn(
                session,
                assistant_text=assistant_text,
                model_message_payloads=model_message_payloads,
                usage=usage,
                message_id=message_id,
            )
            persist = await self._write_transition(result)
            if usage is not None:
                await self._write_usage_checkpoint(session_id, usage)
            # Reload checkpoint onto returned snapshot path is not required for API;
            # callers that need it re-load session.
            return persist

    @_serialized_operation
    async def get_context_usage_checkpoint(
        self, session_id: str
    ) -> ContextUsageCheckpoint | None:
        session = await self.load_session(session_id)
        return session.context_usage

    async def record_compaction_event(
        self, session_id: str, *, reason: str, removed_item_count: int
    ) -> PersistResult:
        return await self._mutate(
            session_id,
            lambda s: record_compaction(
                s, reason=reason, removed_item_count=removed_item_count
            ),
        )

    async def replace_model_messages(
        self,
        session_id: str,
        messages: list[ModelMessageRecord],
        *,
        archive_reason: str,
        archived_payload_json: str,
        removed_prefix_count: int = 0,
    ) -> None:
        """Replace model_messages and append a history archive row (one transaction).

        ``removed_prefix_count`` adjusts the usage checkpoint when oldest PAI
        messages were dropped from the front (compaction).
        """
        async with self._db.write_transaction():
            session = await self.load_session(session_id)
            await self.connection.execute(
                "DELETE FROM model_messages WHERE session_id = ?",
                (session_id,),
            )
            for pos, msg in enumerate(messages, start=1):
                await self.connection.execute(
                    """
                    INSERT INTO model_messages (
                        id, session_id, run_id, position, role, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg.id,
                        session_id,
                        msg.run_id,
                        pos,
                        msg.role,
                        msg.payload_json,
                        msg.created_at,
                    ),
                )
            await self.connection.execute(
                """
                INSERT INTO history_archives (id, session_id, reason, archive_json, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (new_id(), session_id, archive_reason, archived_payload_json),
            )
            await self._adjust_usage_checkpoint_after_prefix_drop(
                session_id,
                session.context_usage,
                removed_prefix_count=removed_prefix_count,
                remaining_pai_count=sum(
                    1 for m in messages if m.payload_json.lstrip().startswith("[")
                ),
            )

    async def _mutate(self, session_id: str, fn: Any) -> PersistResult:
        async with self._db.write_transaction():
            session = await self._load_session_for_update(session_id)
            result = fn(session)
            return await self._write_transition(result)

    async def _commit_transition(
        self, result: TransitionResult, *, is_new_session: bool
    ) -> PersistResult:
        async with self._db.write_transaction():
            return await self._write_transition(result, is_new_session=is_new_session)

    async def _load_session_for_update(self, session_id: str) -> SessionState:
        cursor = await self.connection.execute(
            """
            SELECT id, workspace_path, provider, model, phase, active_run_id,
                   revision, latest_event_sequence, created_at, updated_at,
                   last_usage_tokens, last_usage_message_count
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise DomainNotFound(f"session not found: {session_id}")
        return await self._hydrate_session(row)

    async def _hydrate_session(self, row: Any) -> SessionState:
        core = row_session_core(row)
        active_run: RunState | None = None
        if core["active_run_id"]:
            rcur = await self.connection.execute(
                """
                SELECT id, session_id, status, prompt, error_code, error_message,
                       started_at, ended_at
                FROM runs WHERE id = ?
                """,
                (core["active_run_id"],),
            )
            rrow = await rcur.fetchone()
            if rrow is not None:
                active_run = row_run(rrow)

        acur = await self.connection.execute(
            """
            SELECT id, session_id, run_id, tool_call_id, tool_name, request_json,
                   status, decision, summary, created_at, resolved_at
            FROM approvals
            WHERE session_id = ? AND status = ?
            ORDER BY created_at ASC
            """,
            (core["session_id"], ApprovalStatus.PENDING.value),
        )
        approvals = [row_approval(a) for a in await acur.fetchall()]

        tcur = await self.connection.execute(
            """
            SELECT payload_json FROM transcript_items
            WHERE session_id = ?
            ORDER BY position ASC
            """,
            (core["session_id"],),
        )
        transcript: list[TranscriptItem] = [
            parse_transcript_item(t["payload_json"]) for t in await tcur.fetchall()
        ]

        context_usage = None
        tokens = core.get("last_usage_tokens")
        count = core.get("last_usage_message_count")
        if tokens is not None and count is not None and count > 0:
            context_usage = ContextUsageCheckpoint(tokens=int(tokens), message_count=int(count))

        return SessionState(
            session_id=core["session_id"],
            workspace_path=core["workspace_path"],
            provider=core["provider"],
            model=core["model"],
            phase=core["phase"],
            revision=core["revision"],
            latest_event_sequence=core["latest_event_sequence"],
            created_at=core["created_at"],
            updated_at=core["updated_at"],
            active_run=active_run,
            pending_approvals=approvals,
            transcript=transcript,
            context_usage=context_usage,
        )

    async def _write_usage_checkpoint(
        self, session_id: str, usage: dict[str, int | None]
    ) -> None:
        tokens = _usage_total_tokens(usage)
        if tokens is None:
            return
        pai_count = await self._count_pai_model_messages(session_id)
        if pai_count <= 0:
            return
        await self.connection.execute(
            """
            UPDATE sessions
            SET last_usage_tokens = ?, last_usage_message_count = ?
            WHERE id = ?
            """,
            (tokens, pai_count, session_id),
        )

    async def _count_pai_model_messages(self, session_id: str) -> int:
        cursor = await self.connection.execute(
            """
            SELECT payload_json FROM model_messages
            WHERE session_id = ?
            ORDER BY position ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()
        return sum(1 for r in rows if str(r["payload_json"]).lstrip().startswith("["))

    async def _adjust_usage_checkpoint_after_prefix_drop(
        self,
        session_id: str,
        previous: ContextUsageCheckpoint | None,
        *,
        removed_prefix_count: int,
        remaining_pai_count: int,
    ) -> None:
        if previous is None:
            await self.connection.execute(
                """
                UPDATE sessions
                SET last_usage_tokens = NULL, last_usage_message_count = NULL
                WHERE id = ?
                """,
                (session_id,),
            )
            return
        new_count = previous.message_count - max(0, removed_prefix_count)
        if new_count <= 0 or remaining_pai_count <= 0:
            await self.connection.execute(
                """
                UPDATE sessions
                SET last_usage_tokens = NULL, last_usage_message_count = NULL
                WHERE id = ?
                """,
                (session_id,),
            )
            return
        new_count = min(new_count, remaining_pai_count)
        await self.connection.execute(
            """
            UPDATE sessions
            SET last_usage_tokens = ?, last_usage_message_count = ?
            WHERE id = ?
            """,
            (previous.tokens, new_count, session_id),
        )

    async def _write_transition(
        self,
        result: TransitionResult,
        *,
        is_new_session: bool = False,
    ) -> PersistResult:
        session = result.session
        conn = self.connection

        if is_new_session:
            await conn.execute(
                """
                INSERT INTO sessions (
                    id, workspace_path, provider, model, phase, active_run_id,
                    revision, latest_event_sequence, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.workspace_path,
                    session.provider.value,
                    session.model,
                    session.phase.value,
                    session.active_run.run_id if session.active_run else None,
                    session.revision,
                    session.latest_event_sequence,
                    session.created_at,
                    session.updated_at,
                ),
            )
        else:
            await conn.execute(
                """
                UPDATE sessions SET
                    phase = ?,
                    active_run_id = ?,
                    revision = ?,
                    latest_event_sequence = ?,
                    updated_at = ?,
                    provider = ?,
                    model = ?,
                    workspace_path = ?
                WHERE id = ?
                """,
                (
                    session.phase.value,
                    session.active_run.run_id if session.active_run else None,
                    session.revision,
                    session.latest_event_sequence,  # will update again after events
                    session.updated_at,
                    session.provider.value,
                    session.model,
                    session.workspace_path,
                    session.session_id,
                ),
            )

        if result.new_run is not None:
            run = result.new_run
            await conn.execute(
                """
                INSERT INTO runs (
                    id, session_id, status, prompt, error_code, error_message,
                    started_at, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.session_id,
                    run.status.value,
                    run.prompt,
                    run.error_code,
                    run.error_message,
                    run.started_at,
                    run.ended_at,
                ),
            )
        elif result.updated_run is not None:
            run = result.updated_run
            await conn.execute(
                """
                UPDATE runs SET
                    status = ?, error_code = ?, error_message = ?, ended_at = ?
                WHERE id = ?
                """,
                (
                    run.status.value,
                    run.error_code,
                    run.error_message,
                    run.ended_at,
                    run.run_id,
                ),
            )

        # Transcript positions
        if result.transcript_items:
            cur = await conn.execute(
                "SELECT COALESCE(MAX(position), 0) FROM transcript_items WHERE session_id = ?",
                (session.session_id,),
            )
            row = await cur.fetchone()
            next_pos = int(row[0] if row is not None else 0) + 1
            for item in result.transcript_items:
                await conn.execute(
                    """
                    INSERT INTO transcript_items (
                        id, session_id, position, type, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.id,
                        session.session_id,
                        next_pos,
                        item.type.value if hasattr(item.type, "value") else item.type,
                        transcript_item_to_json(item),
                        item.created_at,
                    ),
                )
                next_pos += 1

        if result.model_messages:
            cur = await conn.execute(
                "SELECT COALESCE(MAX(position), 0) FROM model_messages WHERE session_id = ?",
                (session.session_id,),
            )
            row = await cur.fetchone()
            next_pos = int(row[0] if row is not None else 0) + 1
            for msg in result.model_messages:
                await conn.execute(
                    """
                    INSERT INTO model_messages (
                        id, session_id, run_id, position, role, payload_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_message_id(),
                        session.session_id,
                        msg.run_id,
                        next_pos,
                        msg.role,
                        msg.payload_json,
                        session.updated_at,
                    ),
                )
                next_pos += 1

        for approval in result.approvals:
            await self._upsert_approval(approval)

        # Assign sequences and insert events
        seq = session.latest_event_sequence
        committed_events: list[EventEnvelope] = []
        for draft in result.events:
            seq += 1
            timestamp = draft.timestamp or session.updated_at
            data_json = event_data_to_json(draft.data)
            await conn.execute(
                """
                INSERT INTO events (
                    session_id, sequence, run_id, type, data_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    seq,
                    draft.run_id,
                    event_type_value(draft.type),
                    data_json,
                    timestamp,
                ),
            )
            committed_events.append(
                parse_event_envelope(
                    session_id=session.session_id,
                    sequence=seq,
                    run_id=draft.run_id,
                    type_value=event_type_value(draft.type),
                    data_json=data_json,
                    created_at=timestamp,
                )
            )

        # Prune old events beyond retention window
        if seq > 0:
            min_keep = max(1, seq - self._event_retention_count + 1)
            await conn.execute(
                "DELETE FROM events WHERE session_id = ? AND sequence < ?",
                (session.session_id, min_keep),
            )

        session.latest_event_sequence = seq
        await conn.execute(
            """
            UPDATE sessions SET
                latest_event_sequence = ?,
                active_run_id = ?,
                phase = ?,
                revision = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                seq,
                session.active_run.run_id if session.active_run else None,
                session.phase.value,
                session.revision,
                session.updated_at,
                session.session_id,
            ),
        )

        return PersistResult(
            snapshot=session_to_snapshot(session),
            events=committed_events,
        )

    async def _upsert_approval(self, approval: ApprovalState) -> None:
        await self.connection.execute(
            """
            INSERT INTO approvals (
                id, session_id, run_id, tool_call_id, tool_name, request_json,
                status, decision, summary, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                decision = excluded.decision,
                resolved_at = excluded.resolved_at
            """,
            (
                approval.approval_id,
                approval.session_id,
                approval.run_id,
                approval.tool_call_id,
                approval.tool_name,
                approval.request_json,
                approval.status.value,
                approval.decision,
                approval.summary,
                approval.created_at,
                approval.resolved_at,
            ),
        )


def _usage_total_tokens(usage: dict[str, int | None]) -> int | None:
    """Normalize provider usage into a single context-size checkpoint."""
    total = usage.get("total_tokens")
    if isinstance(total, int) and total > 0:
        return total
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    parts = [v for v in (input_tokens, output_tokens) if isinstance(v, int) and v >= 0]
    if not parts:
        return None
    summed = sum(parts)
    return summed if summed > 0 else None
