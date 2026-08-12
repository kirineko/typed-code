"""Process-level service ownership and runtime artifact tests."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from typed_code.config.credentials import Credentials
from typed_code.config.settings import Settings
from typed_code.service.app_state import build_app_state
from typed_code.service.runtime_identity import (
    ServiceOwner,
    ServiceOwnershipError,
    load_service_descriptor,
    prepare_runtime_paths,
)


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_runtime_paths_are_private_and_log_is_bounded(tmp_path: Path) -> None:
    data_dir = tmp_path / "profile"
    paths = prepare_runtime_paths(data_dir, max_log_bytes=5)

    assert paths.data_dir == data_dir.resolve()
    assert _mode(paths.data_dir) == 0o700
    assert _mode(paths.runtime_dir) == 0o700
    assert _mode(paths.log_path) == 0o600

    paths.log_path.write_bytes(b"123456")
    prepare_runtime_paths(data_dir, max_log_bytes=5)

    assert paths.log_path.read_bytes() == b""
    assert paths.log_path.with_suffix(".log.1").read_bytes() == b"123456"
    assert _mode(paths.log_path.with_suffix(".log.1")) == 0o600


def test_owner_publishes_identity_and_removes_only_its_descriptor(
    tmp_path: Path,
) -> None:
    owner = ServiceOwner.acquire(tmp_path / "profile")
    descriptor = owner.publish_descriptor("http://127.0.0.1:8741")

    assert descriptor["pid"] == os.getpid()
    assert descriptor["instance_id"] == owner.instance_id
    assert descriptor["data_dir"] == str((tmp_path / "profile").resolve())
    assert descriptor["base_url"] == "http://127.0.0.1:8741"
    assert load_service_descriptor(owner.paths.descriptor_path) == descriptor
    assert _mode(owner.paths.descriptor_path) == 0o600

    owner.close()
    assert not owner.paths.descriptor_path.exists()


def test_stale_descriptor_is_replaced_after_lock_acquisition(tmp_path: Path) -> None:
    paths = prepare_runtime_paths(tmp_path / "profile")
    paths.descriptor_path.write_text(
        f'{{"pid":{os.getpid()},"instance_id":"stale","data_dir":"elsewhere"}}',
        encoding="utf-8",
    )

    owner = ServiceOwner.acquire(paths.data_dir)
    try:
        assert not paths.descriptor_path.exists()
        current = owner.publish_descriptor("http://127.0.0.1:9999")
        assert current["instance_id"] != "stale"
    finally:
        owner.close()


def test_one_process_owns_each_data_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "shared"
    script = """
import signal
import sys
from typed_code.service.runtime_identity import ServiceOwner
owner = ServiceOwner.acquire(sys.argv[1])
print('ready', flush=True)
signal.pause()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(data_dir)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "ready"
        with pytest.raises(ServiceOwnershipError) as exc_info:
            ServiceOwner.acquire(data_dir)
        assert exc_info.value.owner is not None
        assert exc_info.value.owner["pid"] == child.pid

        independent = ServiceOwner.acquire(tmp_path / "other")
        independent.close()
    finally:
        child.terminate()
        child.wait(timeout=5)

    recovered = ServiceOwner.acquire(data_dir)
    recovered.close()


async def test_service_lock_precedes_database_open_and_recovery(tmp_path: Path) -> None:
    data_dir = tmp_path / "profile"
    owner = ServiceOwner.acquire(data_dir)
    settings = Settings(data_dir=data_dir)
    credentials = Credentials(
        server_token=SecretStr("test-token"),
        server_token_present=True,
    )
    try:
        with pytest.raises(ServiceOwnershipError):
            await build_app_state(settings=settings, credentials=credentials)
        assert not (data_dir / "typed-code.db").exists()
    finally:
        owner.close()
