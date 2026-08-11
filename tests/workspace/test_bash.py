"""Bash execution tests."""

from __future__ import annotations

import asyncio
import os
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
async def test_run_bash_bounds_streams_while_counting_full_output(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    bash = detect_bash("/bin/bash")

    result = await run_bash(
        bash_executable=bash,
        workspace=root,
        command="python -c \"import sys; sys.stdout.write('x' * 2000000)\"",
        max_stdout_bytes=101,
        max_stderr_bytes=100,
    )

    assert result.exit_code == 0
    assert result.stdout == "x" * 101
    assert result.stdout_truncation.truncated is True
    assert result.stdout_truncation.original_bytes == 2_000_000


@pytest.mark.asyncio
async def test_task_cancellation_terminates_bash_process(tmp_path: Path) -> None:
    root = normalize_workspace_root(tmp_path)
    bash = detect_bash("/bin/bash")
    pid_file = root / "shell.pid"
    run = asyncio.create_task(
        run_bash(
            bash_executable=bash,
            workspace=root,
            command="echo $$ > shell.pid; sleep 30",
            max_stdout_bytes=1000,
            max_stderr_bytes=1000,
        )
    )
    for _ in range(100):
        if pid_file.exists():
            break
        await asyncio.sleep(0.01)
    assert pid_file.exists()
    pid = int(pid_file.read_text().strip())

    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run

    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


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
