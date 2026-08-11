"""Bash execution tests."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from typed_code.workspace.bash import detect_bash, filter_environment, run_bash
from typed_code.workspace.paths import normalize_workspace_root


def test_detect_bash() -> None:
    path = detect_bash("/bin/bash")
    assert path.is_file()


def test_filter_environment_strips_secrets() -> None:
    env = filter_environment(
        {
            "PATH": "/bin",
            "DEEPSEEK_API_KEY": "secret",
            "TYPED_CODE_SERVER_TOKEN": "tok",
            "HOME": "/tmp",
        }
    )
    assert "DEEPSEEK_API_KEY" not in env
    assert "TYPED_CODE_SERVER_TOKEN" not in env
    assert env["PATH"] == "/bin"


@pytest.mark.asyncio
async def test_run_bash_echo(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    bash = detect_bash("/bin/bash")
    result = await run_bash(
        bash_executable=bash,
        workspace=root,
        command="echo hello && pwd",
        max_stdout_bytes=10_000,
        max_stderr_bytes=10_000,
    )
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert str(root) in result.stdout or result.stdout.strip().endswith(root.name)


@pytest.mark.asyncio
async def test_run_bash_cancel(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    bash = detect_bash("/bin/bash")
    cancel = asyncio.Event()

    async def cancel_soon() -> None:
        await asyncio.sleep(0.1)
        cancel.set()

    task = asyncio.create_task(cancel_soon())
    result = await run_bash(
        bash_executable=bash,
        workspace=root,
        command="sleep 30",
        max_stdout_bytes=1000,
        max_stderr_bytes=1000,
        cancel_event=cancel,
    )
    await task
    assert result.cancelled is True
    assert result.exit_code is not None
