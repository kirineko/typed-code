"""Pydantic AI runtime adapter: history → run → public activity."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, cast

from pydantic_ai import (
    Agent,
    DeferredToolRequests,
    DeferredToolResults,
    ToolApproved,
    ToolDenied,
)
from pydantic_ai.models import Model

from typed_code.compaction.compact import compact_messages
from typed_code.config.settings import Settings
from typed_code.domain.errors import DomainConflict
from typed_code.domain.transitions import ModelMessageDraft
from typed_code.persistence.repository import PersistResult, SessionRepository
from typed_code.protocol.common import ApprovalDecision, ProviderName, SessionPhase
from typed_code.protocol.errors import ErrorCode, StructuredError
from typed_code.providers.catalog import ModelCatalog, ResolvedModel
from typed_code.providers.factories import build_responses_model
from typed_code.providers.profiles import profile_for
from typed_code.providers.settings_normalize import (
    EffectiveRunSettings,
    ModelSelectionError,
    RunSettingRequest,
    normalize_settings,
)
from typed_code.runtime.cancellation import RunCancelScope
from typed_code.runtime.history import dumps_messages, loads_messages
from typed_code.runtime.tools import (
    WorkspaceToolDeps,
    approval_request_json,
    bind_workspace_tools,
)
from typed_code.workspace.backend import LocalBashExecutionBackend
from typed_code.workspace.locks import WorkspaceGateRegistry
from typed_code.workspace.policy import tool_summary


def _make_workspace_agent(model: Model, system_prompt: str) -> Agent[WorkspaceToolDeps, Any]:
    """Construct a tools-enabled agent (kwargs path avoids PAI generic overload noise)."""
    kwargs: dict[str, Any] = {
        "system_prompt": system_prompt,
        "deps_type": WorkspaceToolDeps,
        "output_type": [str, DeferredToolRequests],
    }
    agent = Agent(model, **kwargs)
    return cast(Agent[WorkspaceToolDeps, Any], agent)


def _sanitize_error_message(exc: BaseException) -> str:
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    for needle in ("api_key", "authorization", "bearer ", "sk-"):
        if needle in lowered:
            return f"{type(exc).__name__}: provider request failed"
    if len(text) > 300:
        return text[:297] + "..."
    return text


@dataclass
class TurnResult:
    start: PersistResult
    final: PersistResult
    effective_settings: EffectiveRunSettings
    compacted: bool = False
    awaiting_approval: bool = False


@dataclass
class AgentRuntime:
    """Server-side agent execution against a SessionRepository."""

    repository: SessionRepository  # PublishingRepository is duck-typed compatible
    catalog: ModelCatalog
    settings: Settings | None = None
    model_override: Model | None = None
    system_prompt: str = (
        "You are a coding agent. Prefer workspace tools for files and shell. "
        "Be concise and correct."
    )
    enable_workspace_tools: bool = True
    auto_approve_mutations: bool = False
    _cancels: dict[str, RunCancelScope] = field(default_factory=dict)
    _gates: WorkspaceGateRegistry = field(default_factory=WorkspaceGateRegistry)
    _backends: dict[str, LocalBashExecutionBackend] = field(default_factory=dict)

    def _settings(self) -> Settings:
        if self.settings is not None:
            return self.settings
        return self.catalog.settings

    def reload_settings(self, settings: Settings) -> None:
        """Apply reloaded settings and invalidate settings-bound workspace backends."""
        self.settings = settings
        self._backends.clear()

    def cancel_scope(self, session_id: str) -> RunCancelScope:
        scope = self._cancels.get(session_id)
        if scope is None:
            scope = RunCancelScope()
            self._cancels[session_id] = scope
        return scope

    async def cancel(self, session_id: str) -> PersistResult:
        scope = self.cancel_scope(session_id)
        scope.request_cancel()
        return await self._cancel_or_snapshot(session_id)

    async def _cancel_or_snapshot(self, session_id: str) -> PersistResult:
        try:
            return await self.repository.cancel_run(session_id)
        except DomainConflict:
            snap = await self.repository.get_snapshot(session_id)
            return PersistResult(snapshot=snap, events=[])

    async def run_turn(
        self,
        session_id: str,
        prompt: str,
        *,
        setting_request: RunSettingRequest | None = None,
    ) -> TurnResult:
        session = await self.repository.load_session(session_id)
        if session.phase is not SessionPhase.IDLE:
            raise DomainConflict("session already has an active run")

        resolved = self.catalog.resolve(session.provider, session.model)
        api_key = self._api_key(resolved)
        profile = profile_for(resolved.provider, resolved.model_id)
        effective = normalize_settings(
            profile, model_id=resolved.model_id, requested=setting_request
        )

        start = await self.repository.start_turn(session_id, prompt)
        scope = self.cancel_scope(session_id)
        scope.reset()
        run_id = (
            start.snapshot.active_run.run_id
            if start.snapshot.active_run is not None
            else (start.events[0].run_id if start.events else None)
        )

        compacted = False
        try:
            message_history, compacted = await self._prepare_history(
                session_id, effective
            )
            agent, deps = await self._build_agent(
                session.workspace_path, resolved, api_key, scope
            )

            if scope.is_cancelled():
                final = await self._cancel_or_snapshot(session_id)
                return TurnResult(
                    start=start, final=final, effective_settings=effective, compacted=compacted
                )

            try:
                result = await agent.run(
                    prompt, message_history=message_history, deps=deps
                )
            except asyncio.CancelledError:
                final = await self._cancel_or_snapshot(session_id)
                return TurnResult(
                    start=start,
                    final=final,
                    effective_settings=effective,
                    compacted=compacted,
                )

            if scope.is_cancelled():
                final = await self._cancel_or_snapshot(session_id)
                return TurnResult(
                    start=start,
                    final=final,
                    effective_settings=effective,
                    compacted=compacted,
                )

            return await self._handle_agent_result(
                session_id=session_id,
                start=start,
                run_id=run_id,
                message_history=message_history,
                result=result,
                agent=agent,
                deps=deps,
                effective=effective,
                compacted=compacted,
                scope=scope,
            )
        except DomainConflict:
            raise
        except asyncio.CancelledError:
            final = await self._cancel_or_snapshot(session_id)
            return TurnResult(
                start=start,
                final=final,
                effective_settings=effective,
                compacted=compacted,
            )
        except Exception as exc:
            if scope.is_cancelled():
                final = await self._cancel_or_snapshot(session_id)
                return TurnResult(
                    start=start,
                    final=final,
                    effective_settings=effective,
                    compacted=compacted,
                )
            message = _sanitize_error_message(exc)
            final = await self._fail(session_id, ErrorCode.RUN_FAILED, message)
            return TurnResult(
                start=start,
                final=final,
                effective_settings=effective,
                compacted=compacted,
            )

    async def resume_after_approval(
        self,
        session_id: str,
        *,
        approval_id: str,
        decision: ApprovalDecision,
    ) -> TurnResult:
        """Resume a run paused on approval-gated tools."""
        session = await self.repository.load_session(session_id)
        if session.phase is not SessionPhase.AWAITING_APPROVAL:
            raise DomainConflict("session is not awaiting approval")
        if session.active_run is None:
            raise DomainConflict("session has no active run")

        resolved = self.catalog.resolve(session.provider, session.model)
        api_key = self._api_key(resolved)
        profile = profile_for(resolved.provider, resolved.model_id)
        effective = normalize_settings(profile, model_id=resolved.model_id)

        # Map approval_id → tool_call_id from pending approval request_json
        pending = next(
            (a for a in session.pending_approvals if a.approval_id == approval_id),
            None,
        )
        if pending is None:
            raise DomainConflict("approval is not pending for this session")

        payload = json.loads(pending.request_json)
        tool_call_id = str(payload.get("tool_call_id") or pending.tool_call_id)

        resolved_persist = await self.repository.resolve_approval(
            session_id, approval_id=approval_id, decision=decision
        )

        # If still other pending approvals, wait for more decisions
        snap = resolved_persist.snapshot
        if snap.phase is SessionPhase.AWAITING_APPROVAL and snap.pending_approvals:
            return TurnResult(
                start=resolved_persist,
                final=resolved_persist,
                effective_settings=effective,
                awaiting_approval=True,
            )

        # All pending cleared — resume with every decision for this run
        decision_map = await self.repository.list_run_approval_decisions(
            session_id, run_id=session.active_run.run_id
        )
        if tool_call_id not in decision_map:
            decision_map[tool_call_id] = decision is ApprovalDecision.APPROVE
        approvals_map = {
            tid: (ToolApproved() if ok else ToolDenied(message="rejected by user"))
            for tid, ok in decision_map.items()
        }
        deferred = DeferredToolResults(
            approvals=cast(dict[str, bool | ToolApproved | ToolDenied], approvals_map)
        )

        scope = self.cancel_scope(session_id)
        agent, deps = await self._build_agent(
            session.workspace_path, resolved, api_key, scope
        )
        history_records = await self.repository.list_model_messages(session_id)
        pai = [r for r in history_records if r.payload_json.lstrip().startswith("[")]
        message_history = loads_messages(pai) if pai else None

        result = await agent.run(
            message_history=message_history,
            deferred_tool_results=deferred,
            deps=deps,
        )

        # Synthetic start for TurnResult
        start = resolved_persist
        run_id = session.active_run.run_id
        return await self._handle_agent_result(
            session_id=session_id,
            start=start,
            run_id=run_id,
            message_history=message_history,
            result=result,
            agent=agent,
            deps=deps,
            effective=effective,
            compacted=False,
            scope=scope,
        )

    async def _prepare_history(
        self, session_id: str, effective: EffectiveRunSettings
    ) -> tuple[list[Any] | None, bool]:
        compacted = False
        history_records = await self.repository.list_model_messages(session_id)
        pai_history_records = [
            r for r in history_records if r.payload_json.lstrip().startswith("[")
        ]

        budget = effective.profile.context_token_budget
        checkpoint = await self.repository.get_context_usage_checkpoint(session_id)
        last_usage_tokens = checkpoint.tokens if checkpoint else None
        last_usage_index = None
        if checkpoint is not None and checkpoint.message_count > 0:
            last_usage_index = min(checkpoint.message_count, len(pai_history_records)) - 1
            if last_usage_index < 0:
                last_usage_index = None
                last_usage_tokens = None

        compaction = compact_messages(
            pai_history_records,
            token_budget=budget,
            last_usage_tokens=last_usage_tokens,
            last_usage_index=last_usage_index,
        )
        if compaction.removed:
            await self.repository.replace_model_messages(
                session_id,
                compaction.kept,
                archive_reason="context_budget",
                archived_payload_json=json.dumps(
                    [m.payload_json for m in compaction.removed]
                ),
                removed_prefix_count=compaction.removed_item_count,
            )
            await self.repository.record_compaction_event(
                session_id,
                reason="context_budget",
                removed_item_count=compaction.removed_item_count,
            )
            compacted = True
            pai_history_records = compaction.kept

        message_history = (
            loads_messages(pai_history_records) if pai_history_records else None
        )
        return message_history, compacted

    async def _build_agent(
        self,
        workspace_path: str,
        resolved: ResolvedModel,
        api_key: str,
        scope: RunCancelScope,
    ) -> tuple[Agent[Any, Any], WorkspaceToolDeps | None]:
        model = self.model_override or build_responses_model(resolved, api_key=api_key)
        use_tools = self.enable_workspace_tools
        if use_tools:
            from pathlib import Path

            if not Path(workspace_path).expanduser().exists():
                use_tools = False

        if not use_tools:
            agent: Agent[None, str] = Agent(
                model, system_prompt=self.system_prompt, output_type=str
            )
            return agent, None

        backend = await self._backend_for(workspace_path)
        deps = WorkspaceToolDeps(backend, cancel_event=scope._event)
        agent_ws = _make_workspace_agent(model, self.system_prompt)
        bind_workspace_tools(agent_ws)
        return cast(Agent[Any, Any], agent_ws), deps

    async def _backend_for(self, workspace_path: str) -> LocalBashExecutionBackend:
        key = workspace_path
        if key not in self._backends:
            self._backends[key] = await LocalBashExecutionBackend.create_async(
                workspace_path, self._settings(), gates=self._gates
            )
        return self._backends[key]

    async def _handle_agent_result(
        self,
        *,
        session_id: str,
        start: PersistResult,
        run_id: str | None,
        message_history: list[Any] | None,
        result: Any,
        agent: Agent[Any, Any],
        deps: WorkspaceToolDeps | None,
        effective: EffectiveRunSettings,
        compacted: bool,
        scope: RunCancelScope,
    ) -> TurnResult:
        # Auto-approve loop for tests / trusted mode
        while isinstance(result.output, DeferredToolRequests) and self.auto_approve_mutations:
            approvals_map = {
                part.tool_call_id: ToolApproved() for part in result.output.approvals
            }
            result = await agent.run(
                message_history=result.all_messages(),
                deferred_tool_results=DeferredToolResults(
                    approvals=cast(
                        dict[str, bool | ToolApproved | ToolDenied],
                        approvals_map,
                    )
                ),
                deps=deps,
            )

        if scope.is_cancelled():
            final = await self.repository.cancel_run(session_id)
            return TurnResult(
                start=start, final=final, effective_settings=effective, compacted=compacted
            )

        if isinstance(result.output, DeferredToolRequests):
            return await self._pause_for_approvals(
                session_id=session_id,
                start=start,
                run_id=run_id,
                message_history=message_history,
                result=result,
                effective=effective,
                compacted=compacted,
            )

        all_msgs = list(result.all_messages())
        prior_count = len(message_history or [])
        new_msgs = all_msgs[prior_count:]
        drafts = [
            ModelMessageDraft(role=d.role, payload_json=d.payload_json, run_id=run_id)
            for d in dumps_messages(new_msgs)
        ]
        usage_obj = result.usage
        usage = {
            "input_tokens": getattr(usage_obj, "input_tokens", None),
            "output_tokens": getattr(usage_obj, "output_tokens", None),
            "total_tokens": getattr(usage_obj, "total_tokens", None),
        }
        text = result.output if isinstance(result.output, str) else str(result.output)
        final = await self.repository.finish_assistant_turn(
            session_id,
            assistant_text=text,
            model_message_payloads=drafts,
            usage=usage,
        )
        return TurnResult(
            start=start,
            final=final,
            effective_settings=effective,
            compacted=compacted,
            awaiting_approval=False,
        )

    async def _pause_for_approvals(
        self,
        *,
        session_id: str,
        start: PersistResult,
        run_id: str | None,
        message_history: list[Any] | None,
        result: Any,
        effective: EffectiveRunSettings,
        compacted: bool,
    ) -> TurnResult:
        # Persist history up to the deferred tool call
        all_msgs = list(result.all_messages())
        prior_count = len(message_history or [])
        new_msgs = all_msgs[prior_count:]
        drafts = [
            ModelMessageDraft(role=d.role, payload_json=d.payload_json, run_id=run_id)
            for d in dumps_messages(new_msgs)
        ]
        if drafts:
            await self.repository.append_model_messages(session_id, drafts)

        deferred: DeferredToolRequests = result.output
        last = start
        for part in deferred.approvals:
            args = part.args if isinstance(part.args, dict) else {}
            summary = tool_summary(part.tool_name, args)
            last = await self.repository.request_approval(
                session_id,
                tool_call_id=part.tool_call_id,
                tool_name=part.tool_name,
                summary=summary,
                request_json=approval_request_json(
                    part.tool_name, args, part.tool_call_id
                ),
            )

        return TurnResult(
            start=start,
            final=last,
            effective_settings=effective,
            compacted=compacted,
            awaiting_approval=True,
        )

    async def _fail(
        self, session_id: str, code: ErrorCode, message: str
    ) -> PersistResult:
        error = StructuredError(code=code, message=message)
        try:
            return await self.repository.fail_run(session_id, error)
        except DomainConflict:
            snap = await self.repository.get_snapshot(session_id)
            return PersistResult(snapshot=snap, events=[])

    def _api_key(self, resolved: ResolvedModel) -> str:
        creds = self.catalog.credentials
        if resolved.provider is ProviderName.DEEPSEEK:
            key = creds.deepseek_api_key
        else:
            key = creds.cliproxy_api_key
        if key is None:
            err = ModelSelectionError("provider credentials are missing")
            err.code = ErrorCode.MISSING_CREDENTIALS
            raise err
        return key.get_secret_value()
