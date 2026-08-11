"""Bash execution with workspace cwd and process-tree cancellation."""

from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from pathlib import Path

from typed_code.workspace.bounds import TruncationInfo, truncate_bytes
from typed_code.workspace.errors import BashUnavailableError

_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "TMPDIR",
        "TMP",
        "TEMP",
        "SHELL",
    }
)

_ENV_DENY_PREFIXES = (
    "DEEPSEEK_",
    "OPENAI_",
    "ANTHROPIC_",
    "TYPED_CODE_",
    "CLIPROXY_",
    "AWS_",
    "GOOGLE_",
)


@dataclass(frozen=True)
class BashResult:
    command: str
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncation: TruncationInfo
    stderr_truncation: TruncationInfo
    cancelled: bool = False


def detect_bash(executable: str) -> Path:
    path = Path(executable).expanduser()
    if not path.is_absolute():
        # Search PATH
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(directory) / executable
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate.resolve()
        raise BashUnavailableError(f"bash executable not found on PATH: {executable}")
    if not path.is_file() or not os.access(path, os.X_OK):
        raise BashUnavailableError(f"bash executable not usable: {path}")
    return path.resolve()


def filter_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    env_in = source if source is not None else dict(os.environ)
    out: dict[str, str] = {}
    for key, value in env_in.items():
        if key.startswith(_ENV_DENY_PREFIXES):
            continue
        if key in _ENV_ALLOWLIST or key.startswith("LC_"):
            out[key] = value
    # Ensure a minimal PATH
    out.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    return out


async def run_bash(
    *,
    bash_executable: Path,
    workspace: Path,
    command: str,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    cancel_event: asyncio.Event | None = None,
) -> BashResult:
    if not command.strip():
        raise BashUnavailableError("command must be non-empty")

    env = filter_environment()
    proc = await asyncio.create_subprocess_exec(
        str(bash_executable),
        "--noprofile",
        "--norc",
        "-c",
        command,
        cwd=str(workspace),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    cancelled = False

    async def _watch_cancel() -> None:
        nonlocal cancelled
        if cancel_event is None:
            return
        await cancel_event.wait()
        cancelled = True
        await _kill_process_tree(proc)

    watcher: asyncio.Task[None] | None = None
    if cancel_event is not None:
        watcher = asyncio.create_task(_watch_cancel())

    try:
        stdout_b, stderr_b = await proc.communicate()
    finally:
        if watcher is not None:
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass

    stdout_cap, stdout_tr = truncate_bytes(stdout_b or b"", max_bytes=max_stdout_bytes)
    stderr_cap, stderr_tr = truncate_bytes(stderr_b or b"", max_bytes=max_stderr_bytes)

    return BashResult(
        command=command,
        exit_code=proc.returncode,
        stdout=stdout_cap.decode("utf-8", errors="replace"),
        stderr=stderr_cap.decode("utf-8", errors="replace"),
        stdout_truncation=stdout_tr,
        stderr_truncation=stderr_tr,
        cancelled=cancelled,
    )


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    pid = proc.pid
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
        return
    except (TimeoutError, ProcessLookupError):
        pass
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=1.0)
    except (TimeoutError, ProcessLookupError):
        pass
