# Implementation Verification

## 2026-08-11 macOS Apple Silicon freezer spike

Host: Darwin 25.5.0, Apple M4 Pro arm64, Python 3.13.13.

### PyInstaller 6.22.0

- Final one-file artifact: `/tmp/typed-code-pyinstaller/dist/typed-code-server`
- Size: 28,516,160 bytes.
- Final incremental build: 20.92 seconds.
- Required packaging inputs: `typed_code` migration SQL data, recursive `pydantic-ai-slim` distribution metadata, `genai-prices` and `typed-code` metadata, all `pydantic_ai` and `tiktoken` modules/data.
- Initial runtime failures identified and repaired: missing `genai_prices` distribution metadata, then missing `typed_code/persistence/migrations/*.sql`.
- `version` first/second launch: 15.39/7.33 seconds; maximum RSS 44,236,800/46,399,488 bytes.
- Frozen service authenticated-health readiness: 16.2 seconds on the first complete build and 12.4 seconds on the controlled-provider build.
- Service child RSS: 113,200 KiB after initial health; 168,640 KiB after three controlled sessions covering text, thinking, and approval continuation.
- Controlled verification passed: authenticated health, SQLite migration, full Responses text/thinking streaming, loaded native `tiktoken` extension, deferred Bash approval, approved Bash execution in `/tmp`, assistant completion, and persistent session snapshots. A real HTTPS request reached DeepSeek and returned the expected HTTP 401 for the intentionally invalid key, proving bundled TLS/certificate loading rather than a certificate failure. After service shutdown, SQLite reported `integrity_check=ok` with all four controlled sessions idle.

### Nuitka 4.1.3

- Final one-file artifact: `/tmp/typed-code-nuitka/typed-code-server`
- Size: 39,422,944 bytes.
- Final build: 368.44 seconds without `ccache`.
- Required packaging inputs: explicit `typed_code/persistence/migrations` data directory, `pydantic_ai` and `tiktoken` packages/data, and bundled `certifi/cacert.pem`.
- Initial runtime failure identified and repaired: missing `typed_code/persistence/migrations/*.sql`.
- `version` first/second launch: 5.73/3.04 seconds; maximum RSS 175,538,176 bytes.
- Frozen service authenticated-health readiness: 24.0 seconds.
- Service child RSS after initial health: 175,504 KiB.
- Controlled local verification passed: authenticated health, SQLite migration, Responses streaming, deferred Bash approval, approved Bash execution, assistant completion, and persistent session snapshots; SQLite reported `integrity_check=ok` after shutdown. The HTTPS negative-path probe failed incorrectly with `RuntimeError: No active exception to reraise` instead of preserving the upstream HTTP 401, so this Nuitka artifact does not satisfy the TLS/error-handling gate.

### Preliminary result

PyInstaller is the only candidate that satisfies the complete development-host runtime gate. Its final artifact is 27.7% smaller, builds approximately 17.6 times faster in the measured no-`ccache` environment, uses less initial service memory, and preserves HTTPS provider errors correctly. Nuitka starts the trivial `version` command faster but fails the HTTPS negative path and is rejected. Clean-host, quarantine, signing/notarization, and packed-install checks remain before production support is claimed.

### Isolated-host simulation and macOS trust

- Copied the PyInstaller artifact into `/tmp/typed-code-clean-host`, outside the source checkout.
- Ran `version` and started authenticated health with `env -i`, `PATH=/usr/bin:/bin`, an isolated `HOME`, isolated XDG roots, and no Python or `uv` on `PATH`; both passed.
- `otool -L` reports only `/usr/lib/libSystem.B.dylib` and `/usr/lib/libz.1.dylib`, with no external Python runtime dependency.
- Executable mode `0755` was preserved by the copy.
- Adding a synthetic `com.apple.quarantine` attribute did not prevent direct terminal execution on this development host.
- PyInstaller's ad-hoc signature passes `codesign --verify --deep --strict` but `spctl --assess --type execute` rejects it. Therefore the public artifact must use Developer ID Application signing and Apple notarization; ad-hoc signing is development-only.
- This isolated process test is not evidence from a separate clean macOS installation. The release workflow must repeat the packed npm install and Gatekeeper checks on a fresh Apple Silicon host before production support is claimed.

### Freezer and trust decision

Select PyInstaller 6.22.0 for `@typed-code/server-darwin-arm64`. Reject Nuitka 4.1.3 because it fails the provider HTTPS error path and offers no compensating size, build-time, or service-memory advantage. Sign the PyInstaller build and all collected Mach-O inputs with Developer ID Application in release CI, submit the exact executable in a notarization archive, and package only the verified executable into npm.


## 2026-08-11 completion evidence

### Distribution artifacts

- `npm run pack:release` produced version-aligned `0.1.0` packages: CLI 70,923 bytes, SDK 18,630 bytes, and Darwin ARM64 companion 28,202,958 bytes.
- Two consecutive release builds produced identical SHA-256 values: CLI `d7595df873da14cde6d19e5f601d88b77b139e922810751dc2498bd8bc5d3643`, SDK `d1213404efd48297549c75b128d6a540206e85bfdfa753c6c5552374606f5fc6`, and companion `d4ca27eb097dfc15077f77c597b2a77d0db9078011a2e053baef2c38822de4fe`.
- The companion npm archive preserves executable mode `0755`; its unpacked size is 28,537,535 bytes. Package validation accepts only the `typed-code` CLI bin, same-version companion dependency, matching Python/SDK protocol version, and matching service release.
- Release CI builds on `macos-15`, requires Developer ID and notarization credentials on every invocation, signs and verifies the exact companion, submits that executable in a notarization archive, checks the accepted executable with Gatekeeper, then packs the unchanged executable and verifies checksums. Signing/notarization credentials were not available in this workstation, so CI execution with real Apple credentials remains a release-time external check.

### Isolated packed installation

- Installed all three local tarballs into `/tmp/typed-code-clean-install/app`; launched from `/tmp/typed-code-clean-install/workspace` with isolated HOME/XDG roots and a `PATH` containing Node and system tools but no Python or `uv`.
- Cold packaged startup reached the TUI in 24.5 seconds. The first client streamed thinking and assistant output, persisted the session, and exited. A second packaged client resumed the same session, displayed and approved a Bash tool request, observed assistant completion, and created the expected `frozen-tool.txt` side effect.
- After both clients exited, `typed-code server status` reported the persistent service with zero active work and `typed-code server stop` shut it down cleanly.
- This is a clean installation prefix and unrelated workspace on the Apple M4 Pro host, not a second physical Mac. The signed/notarized clean-host Gatekeeper run is therefore intentionally retained in release CI.

### Live provider and terminal scenarios

- `uv run typed-code smoke cliproxy` completed against the configured live Responses provider in 8.49 seconds: provider `cliproxy`, model `gpt-5.6-terra`, status `ok`, output length 2. No credential was printed.
- Two real pi-tui clients attached to session `b37c28575802461cb502e37fb71ecc66` from `/tmp/typed-code-terminal-multi/workspace`. Client B reconstructed an awaiting Bash approval, client A exited with code 0, client B approved the tool and observed the run reach `Ready`; after B exited, `server status` still reported the service running with zero active work.
- A separately started `uv run --project /Users/kirineko/Github/typed-code typed-code serve` accepted a real `typed-code --no-spawn --base-url http://127.0.0.1:18773` TUI client from the unrelated workspace, streamed a complete response, and left the terminal clean on Ctrl+C.
- Separate process scenarios also verified concurrent cold starts, two independent workspaces on one service, authoritative command conflicts, completed replay, and idle policy suppression while runs, approvals, or event streams are active.

### Quality gates and deferred boundaries

- Regenerated `contracts/openapi.v1.json` and `contracts/events.schema.v1.json`; the SDK now exposes the additive service health fields and authenticated `stopService` administration contract.
- Final gates: Ruff passed; `ty` passed; Python passed 137 tests; SDK passed 27 tests including contract drift; CLI passed 75 tests; both TypeScript workspaces built and type-checked.
- Production companion support remains intentionally limited to Darwin ARM64. Linux is source-development-only; Darwin x64 and Windows have no verified companion and fail with detected-platform guidance rather than discovering an arbitrary backend.
- Web UI assets, Web login/session issuance, and broad CORS remain deferred. The implemented boundary is loopback-only, rejects invalid Host/Origin combinations before protected handlers, and exposes no browser method for retrieving the long-lived CLI bearer token.
- `openspec validate add-user-service-launcher --type change --strict --json` passed with one valid change and zero issues.