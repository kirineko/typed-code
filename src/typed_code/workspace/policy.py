"""Tool approval classification."""

from __future__ import annotations

from typed_code.workspace.backend import ExecutionBackend


def requires_approval(tool_name: str) -> bool:
    return tool_name in {"write_file", "edit_file", "bash"}


def tool_summary(tool_name: str, args: dict[str, object]) -> str:
    if tool_name == "read_file":
        return f"read {args.get('path', '?')}"
    if tool_name == "write_file":
        return f"write {args.get('path', '?')}"
    if tool_name == "edit_file":
        return f"edit {args.get('path', '?')}"
    if tool_name == "bash":
        cmd = str(args.get("command", ""))
        preview = " ".join(cmd.split())
        if len(preview) > 80:
            preview = preview[:79] + "…"
        return f"bash: {preview}"
    return tool_name


def format_tool_result(tool_name: str, result: object) -> str:
    if tool_name == "read_file" and hasattr(result, "content"):
        tr = getattr(result, "truncation", None)
        suffix = ""
        if tr is not None and getattr(tr, "truncated", False):
            suffix = (
                f"\n[truncated original_bytes={tr.original_bytes} "
                f"captured_bytes={tr.captured_bytes}]"
            )
        path = getattr(result, "path", "?")
        content = getattr(result, "content", "")
        return f"path={path}\n{content}{suffix}"
    if tool_name == "write_file" and hasattr(result, "path"):
        return (
            f"wrote {getattr(result, 'path', '?')} "
            f"({getattr(result, 'size_bytes', 0)} bytes, "
            f"created={getattr(result, 'created', False)})"
        )
    if tool_name == "edit_file" and hasattr(result, "diff"):
        return f"edited {getattr(result, 'path', '?')}\n{getattr(result, 'diff', '')}"
    if tool_name == "bash" and hasattr(result, "exit_code"):
        return (
            f"exit_code={getattr(result, 'exit_code', None)} "
            f"cancelled={getattr(result, 'cancelled', False)}\n"
            f"stdout:\n{getattr(result, 'stdout', '')}\n"
            f"stderr:\n{getattr(result, 'stderr', '')}"
        )
    return str(result)


# Keep ExecutionBackend import used for type docs
_ = ExecutionBackend
