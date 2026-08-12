"""Build and validate the macOS Apple Silicon service companion."""

from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_ROOT = ROOT / "build" / "companion"
OUTPUT = ROOT / "packages" / "server-darwin-arm64" / "bin" / "typed-code-server"
SPEC = ROOT / "packaging" / "typed-code-server.spec"


def main() -> int:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit(
            f"companion build requires darwin/arm64, got {platform.system()}/{platform.machine()}"
        )
    _require_matching_versions()
    shutil.rmtree(BUILD_ROOT, ignore_errors=True)
    (BUILD_ROOT / "dist").mkdir(parents=True)
    env = {
        **os.environ,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": os.environ.get("SOURCE_DATE_EPOCH", "0"),
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(BUILD_ROOT / "dist"),
            "--workpath",
            str(BUILD_ROOT / "work"),
            str(SPEC),
        ],
        cwd=ROOT,
        env=env,
        check=True,
    )
    built = BUILD_ROOT / "dist" / "typed-code-server"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(built, OUTPUT)
    OUTPUT.chmod(0o755)

    identity = os.environ.get("TYPED_CODE_CODESIGN_IDENTITY", "-")
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", identity, str(OUTPUT)],
        check=True,
    )
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(OUTPUT)], check=True)
    description = subprocess.run(
        ["file", str(OUTPUT)],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout
    if "Mach-O 64-bit executable arm64" not in description:
        raise SystemExit(f"unexpected companion format: {description.strip()}")
    if stat.S_IMODE(OUTPUT.stat().st_mode) != 0o755:
        raise SystemExit("companion executable mode must be 0755")
    version = subprocess.run(
        [str(OUTPUT), "version"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    expected = _package_version(ROOT / "packages" / "server-darwin-arm64" / "package.json")
    if version != expected:
        raise SystemExit(f"companion version mismatch: {version!r}, expected {expected!r}")
    print(OUTPUT)
    return 0


def _require_matching_versions() -> None:
    versions = {
        _package_version(ROOT / "packages" / "cli" / "package.json"),
        _package_version(ROOT / "packages" / "sdk" / "package.json"),
        _package_version(ROOT / "packages" / "server-darwin-arm64" / "package.json"),
        _python_project_version(),
    }
    if len(versions) != 1:
        raise SystemExit(f"release versions do not match: {sorted(versions)}")


def _package_version(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    version = value.get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit(f"package version unavailable: {path}")
    return version


def _python_project_version() -> str:
    import tomllib

    value = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = value.get("project", {}).get("version")
    if not isinstance(version, str) or not version:
        raise SystemExit("Python project version unavailable")
    return version


if __name__ == "__main__":
    raise SystemExit(main())
