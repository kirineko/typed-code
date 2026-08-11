"""Local workspace execution backend."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from typed_code.config.settings import Settings
from typed_code.workspace.bash import BashResult, detect_bash, run_bash
from typed_code.workspace.files import (
    EditResult,
    ReadResult,
    WriteResult,
    edit_text_file,
    read_text_file,
    write_text_file,
)
from typed_code.workspace.locks import WorkspaceGate, WorkspaceGateRegistry
from typed_code.workspace.paths import normalize_workspace_root


class ExecutionBackend(Protocol):
    workspace: Path

    async def read(self, path: str) -> ReadResult: ...
    async def write(self, path: str, content: str) -> WriteResult: ...
    async def edit(
        self, path: str, *, old_string: str, new_string: str
    ) -> EditResult: ...
    async def bash(
        self, command: str, *, cancel_event: asyncio.Event | None = None
    ) -> BashResult: ...


@dataclass
class LocalBashExecutionBackend:
    """Filesystem + Bash backend confined to one workspace."""

    workspace: Path
    settings: Settings
    gate: WorkspaceGate
    bash_executable: Path

    @classmethod
    async def create_async(
        cls,
        workspace: Path | str,
        settings: Settings,
        *,
        gates: WorkspaceGateRegistry | None = None,
    ) -> LocalBashExecutionBackend:
        root = normalize_workspace_root(workspace)
        registry = gates or WorkspaceGateRegistry()
        gate = await registry.gate_for(root)
        bash = detect_bash(settings.bash_executable)
        return cls(
            workspace=root, settings=settings, gate=gate, bash_executable=bash
        )

    async def read(self, path: str) -> ReadResult:
        async with self.gate.reading():
            return await asyncio.to_thread(
                read_text_file,
                self.workspace,
                path,
                max_bytes=self.settings.read_max_bytes,
                max_lines=self.settings.read_max_lines,
            )

    async def write(self, path: str, content: str) -> WriteResult:
        async with self.gate.mutating():
            return await asyncio.to_thread(
                write_text_file, self.workspace, path, content
            )

    async def edit(
        self, path: str, *, old_string: str, new_string: str
    ) -> EditResult:
        async with self.gate.mutating():
            return await asyncio.to_thread(
                edit_text_file,
                self.workspace,
                path,
                old_string=old_string,
                new_string=new_string,
            )

    async def bash(
        self, command: str, *, cancel_event: asyncio.Event | None = None
    ) -> BashResult:
        async with self.gate.mutating():
            return await run_bash(
                bash_executable=self.bash_executable,
                workspace=self.workspace,
                command=command,
                max_stdout_bytes=self.settings.bash_max_stdout_bytes,
                max_stderr_bytes=self.settings.bash_max_stderr_bytes,
                cancel_event=cancel_event,
            )
