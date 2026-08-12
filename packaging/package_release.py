"""Pack and validate version-matched npm release artifacts."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import tarfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = ROOT / "release"
COMPANION = ROOT / "packages" / "server-darwin-arm64" / "bin" / "typed-code-server"
WORKSPACES = (
    "@typed-code/sdk",
    "@typed-code/server-darwin-arm64",
    "@typed-code/cli",
)


def main() -> int:
    _run(["npm", "run", "build"])
    shutil.rmtree(RELEASE_DIR, ignore_errors=True)
    RELEASE_DIR.mkdir(mode=0o755)
    manifests: list[dict[str, Any]] = []
    for workspace in WORKSPACES:
        output = _run(
            [
                "npm",
                "pack",
                "--json",
                "--pack-destination",
                str(RELEASE_DIR),
                "-w",
                workspace,
            ],
            capture=True,
        )
        value = json.loads(output)
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise SystemExit(f"unexpected npm pack output for {workspace}")
        manifests.append(value[0])

    versions = {str(item.get("version")) for item in manifests}
    if len(versions) != 1:
        raise SystemExit(f"packed release versions do not match: {sorted(versions)}")
    version = versions.pop()
    archives = {item["name"]: RELEASE_DIR / str(item["filename"]) for item in manifests}
    _validate_companion_archive(archives["@typed-code/server-darwin-arm64"], version)
    _validate_cli_archive(archives["@typed-code/cli"], version)
    _validate_protocol_identity()

    lines = []
    for archive in sorted(archives.values()):
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        lines.append(f"{digest}  {archive.name}")
    (RELEASE_DIR / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RELEASE_DIR)
    return 0


def _validate_companion_archive(path: Path, version: str) -> None:
    if stat.S_IMODE(COMPANION.stat().st_mode) != 0o755:
        raise SystemExit("companion source executable mode must be 0755")
    if _run([str(COMPANION), "version"], capture=True).strip() != version:
        raise SystemExit("companion executable version does not match npm package")
    with tarfile.open(path, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        binary = members.get("package/bin/typed-code-server")
        if binary is None or not binary.isfile():
            raise SystemExit("companion tarball is missing bin/typed-code-server")
        if binary.mode & 0o777 != 0o755:
            raise SystemExit("packed companion executable mode must be 0755")
        package = _tar_json(archive, "package/package.json")
    if package.get("version") != version:
        raise SystemExit("companion package version mismatch")
    if package.get("os") != ["darwin"] or package.get("cpu") != ["arm64"]:
        raise SystemExit("companion package platform selectors are invalid")


def _validate_cli_archive(path: Path, version: str) -> None:
    with tarfile.open(path, "r:gz") as archive:
        package = _tar_json(archive, "package/package.json")
        members = {member.name: member for member in archive.getmembers()}
    if package.get("bin") != {"typed-code": "./dist/bin.js"}:
        raise SystemExit("CLI tarball must expose only the typed-code bin")
    optional = package.get("optionalDependencies")
    if not isinstance(optional, dict) or optional.get("@typed-code/server-darwin-arm64") != version:
        raise SystemExit("CLI companion dependency must match the release version")
    entry = members.get("package/dist/bin.js")
    if entry is None or not entry.isfile() or entry.mode & 0o111 == 0:
        raise SystemExit("CLI tarball entrypoint is missing or not executable")


def _validate_protocol_identity() -> None:
    python_version = _run(
        [
            "uv",
            "run",
            "python",
            "-c",
            "from typed_code.protocol import PROTOCOL_VERSION; print(PROTOCOL_VERSION)",
        ],
        capture=True,
    ).strip()
    sdk_version = _run(
        [
            "node",
            "--input-type=module",
            "--eval",
            "import('./packages/sdk/dist/version.js').then(m => console.log(m.PROTOCOL_VERSION))",
        ],
        capture=True,
    ).strip()
    if python_version != sdk_version:
        raise SystemExit(
            f"protocol mismatch between service ({python_version}) and SDK ({sdk_version})"
        )


def _tar_json(archive: tarfile.TarFile, name: str) -> dict[str, Any]:
    member = archive.extractfile(name)
    if member is None:
        raise SystemExit(f"tarball is missing {name}")
    value = json.loads(member.read())
    if not isinstance(value, dict):
        raise SystemExit(f"expected JSON object in {name}")
    return value


def _run(argv: list[str], *, capture: bool = False) -> str:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout or ""


if __name__ == "__main__":
    raise SystemExit(main())
