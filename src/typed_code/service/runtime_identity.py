"""User-scoped service runtime paths, ownership, and descriptor publication."""

from __future__ import annotations

import fcntl
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from typed_code import __version__
from typed_code.config.errors import ConfigurationError
from typed_code.domain.clock import isoformat, utc_now
from typed_code.protocol import PROTOCOL_VERSION

DEFAULT_MAX_LOG_BYTES = 5 * 1024 * 1024


class ServiceOwnershipError(ConfigurationError):
    """Raised when another process owns the canonical data directory."""

    def __init__(self, data_dir: Path, owner: dict[str, Any] | None = None) -> None:
        detail = ""
        if owner is not None and isinstance(owner.get("pid"), int):
            detail = f" (pid {owner['pid']})"
        super().__init__(
            "service_already_running",
            f"another typed-code service owns data directory {data_dir}{detail}",
        )
        self.data_dir = data_dir
        self.owner = owner


@dataclass(frozen=True)
class RuntimePaths:
    data_dir: Path
    runtime_dir: Path
    lock_path: Path
    descriptor_path: Path
    log_path: Path


@dataclass
class ServiceOwner:
    """Process-lifetime exclusive owner for one canonical data directory."""

    paths: RuntimePaths
    lock_fd: int
    instance_id: str
    pid: int
    started_at: str
    base_url: str | None = None
    _closed: bool = False

    @classmethod
    def acquire(cls, data_dir: Path | str) -> ServiceOwner:
        paths = prepare_runtime_paths(data_dir)
        fd = os.open(paths.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.fchmod(fd, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                owner = _read_json_fd(fd)
                raise ServiceOwnershipError(paths.data_dir, owner) from exc

            owner = cls(
                paths=paths,
                lock_fd=fd,
                instance_id=uuid4().hex,
                pid=os.getpid(),
                started_at=isoformat(utc_now()),
            )
            owner._write_lock_metadata()
            _remove_stale_descriptor(paths.descriptor_path)
            return owner
        except BaseException:
            os.close(fd)
            raise

    def descriptor(self, *, base_url: str | None = None) -> dict[str, Any]:
        endpoint = self.base_url if base_url is None else base_url
        if endpoint is None:
            raise RuntimeError("service base URL is not available before descriptor publication")
        return {
            "pid": self.pid,
            "instance_id": self.instance_id,
            "base_url": endpoint,
            "service_version": __version__,
            "protocol_version": PROTOCOL_VERSION,
            "data_dir": str(self.paths.data_dir),
            "started_at": self.started_at,
        }

    def publish_descriptor(self, base_url: str) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("cannot publish a descriptor for a closed service owner")
        self.base_url = base_url
        descriptor = self.descriptor()
        _atomic_write_json(self.paths.descriptor_path, descriptor)
        return descriptor

    def matches_descriptor(self, descriptor: dict[str, Any]) -> bool:
        return (
            descriptor.get("instance_id") == self.instance_id
            and descriptor.get("pid") == self.pid
            and descriptor.get("data_dir") == str(self.paths.data_dir)
        )

    def close(self) -> None:
        if self._closed:
            return
        try:
            descriptor = load_service_descriptor(self.paths.descriptor_path)
            if descriptor is not None and self.matches_descriptor(descriptor):
                self.paths.descriptor_path.unlink(missing_ok=True)
        finally:
            fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            os.close(self.lock_fd)
            self._closed = True

    def _write_lock_metadata(self) -> None:
        payload = {
            "pid": self.pid,
            "instance_id": self.instance_id,
            "data_dir": str(self.paths.data_dir),
            "started_at": self.started_at,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        os.lseek(self.lock_fd, 0, os.SEEK_SET)
        os.ftruncate(self.lock_fd, 0)
        os.write(self.lock_fd, encoded)
        os.fsync(self.lock_fd)


def canonical_data_dir(data_dir: Path | str) -> Path:
    """Resolve the absolute service identity without requiring it to exist."""
    return Path(data_dir).expanduser().resolve(strict=False)


def runtime_paths(data_dir: Path | str) -> RuntimePaths:
    canonical = canonical_data_dir(data_dir)
    runtime_dir = canonical / "runtime"
    return RuntimePaths(
        data_dir=canonical,
        runtime_dir=runtime_dir,
        lock_path=runtime_dir / "service.lock",
        descriptor_path=runtime_dir / "service.json",
        log_path=runtime_dir / "server.log",
    )


def prepare_runtime_paths(
    data_dir: Path | str,
    *,
    max_log_bytes: int = DEFAULT_MAX_LOG_BYTES,
) -> RuntimePaths:
    """Create owner-only durable/runtime directories and a bounded log target."""
    paths = runtime_paths(data_dir)
    _ensure_private_directory(paths.data_dir)
    _ensure_private_directory(paths.runtime_dir)
    _prepare_log(paths.log_path, max_log_bytes=max_log_bytes)
    return paths


def load_service_descriptor(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(value, dict):
        return None
    return value


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise ConfigurationError("runtime_path_invalid", f"service path is not a directory: {path}")
    if info.st_uid != os.getuid():
        raise ConfigurationError(
            "runtime_path_wrong_owner",
            f"service path is not owned by the current user: {path}",
        )
    os.chmod(path, 0o700)


def _prepare_log(path: Path, *, max_log_bytes: int) -> None:
    if max_log_bytes < 1:
        raise ValueError("max_log_bytes must be positive")
    try:
        oversized = path.stat().st_size > max_log_bytes
    except FileNotFoundError:
        oversized = False
    if oversized:
        backup = path.with_suffix(path.suffix + ".1")
        backup.unlink(missing_ok=True)
        os.replace(path, backup)
        os.chmod(backup, 0o600)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)


def _read_json_fd(fd: int) -> dict[str, Any] | None:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        raw = os.read(fd, 16_384)
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _remove_stale_descriptor(path: Path) -> None:
    path.unlink(missing_ok=True)


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, encoded)
        os.fsync(fd)
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    try:
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
