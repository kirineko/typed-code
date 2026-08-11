"""Register workspace tools with a Pydantic AI Agent."""

from __future__ import annotations

import json
from typing import Any

from pydantic_ai import Agent, RunContext

from typed_code.workspace.backend import ExecutionBackend
from typed_code.workspace.errors import WorkspaceError
from typed_code.workspace.policy import format_tool_result


class WorkspaceToolDeps:
    """Deps injected into tool calls."""

    def __init__(
        self,
        backend: ExecutionBackend,
        *,
        cancel_event: Any | None = None,
    ) -> None:
        self.backend = backend
        self.cancel_event = cancel_event


def bind_workspace_tools(agent: Agent[WorkspaceToolDeps, Any]) -> None:
    """Register read/write/edit/bash tools. Mutations require approval."""

    @agent.tool
    async def read_file(ctx: RunContext[WorkspaceToolDeps], path: str) -> str:
        """Read a UTF-8 text file from the session workspace."""
        try:
            result = await ctx.deps.backend.read(path)
        except WorkspaceError as exc:
            return f"ERROR[{exc.code}]: {exc.message}"
        return format_tool_result("read_file", result)

    @agent.tool(requires_approval=True)
    async def write_file(
        ctx: RunContext[WorkspaceToolDeps], path: str, content: str
    ) -> str:
        """Create or replace a UTF-8 text file (requires approval)."""
        try:
            result = await ctx.deps.backend.write(path, content)
        except WorkspaceError as exc:
            return f"ERROR[{exc.code}]: {exc.message}"
        return format_tool_result("write_file", result)

    @agent.tool(requires_approval=True)
    async def edit_file(
        ctx: RunContext[WorkspaceToolDeps],
        path: str,
        old_string: str,
        new_string: str,
    ) -> str:
        """Apply a unique string replacement edit (requires approval)."""
        try:
            result = await ctx.deps.backend.edit(
                path, old_string=old_string, new_string=new_string
            )
        except WorkspaceError as exc:
            return f"ERROR[{exc.code}]: {exc.message}"
        return format_tool_result("edit_file", result)

    @agent.tool(requires_approval=True)
    async def bash(ctx: RunContext[WorkspaceToolDeps], command: str) -> str:
        """Run a Bash command in the workspace (requires approval)."""
        try:
            result = await ctx.deps.backend.bash(
                command, cancel_event=ctx.deps.cancel_event
            )
        except WorkspaceError as exc:
            return f"ERROR[{exc.code}]: {exc.message}"
        return format_tool_result("bash", result)


def approval_request_json(tool_name: str, args: dict[str, Any], tool_call_id: str) -> str:
    return json.dumps(
        {"tool_name": tool_name, "args": args, "tool_call_id": tool_call_id},
        ensure_ascii=False,
    )
