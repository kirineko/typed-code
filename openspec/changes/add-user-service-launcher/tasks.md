## 1. macOS Companion Feasibility Gate

- [x] 1.1 Build the current Python service on Apple Silicon with PyInstaller and Nuitka, recording build failures, required hidden imports/assets, artifact size, cold-start time, and steady-state memory for each viable candidate.
- [x] 1.2 Exercise each viable frozen service against health, authentication, SQLite migration, controlled Responses streaming, `tiktoken`, TLS certificate loading, Bash workspace tools, approval continuation, and clean database shutdown.
- [x] 1.3 Run the leading companion on a clean Apple Silicon macOS environment without Python, `uv`, or a typed-code checkout, and document executable permission, quarantine, signing, and notarization findings.
- [x] 1.4 Select and record the freezer and macOS trust strategy; if neither candidate satisfies the gate, stop production-companion work and document the explicitly versioned `uvx` preview fallback without weakening the development or singleton-service scope.

## 2. Service Ownership and Runtime Identity

- [x] 2.1 Add canonical data-directory resolution and an owner-only `${data_dir}/runtime` child containing the service lock, atomic non-secret descriptor, and bounded log without creating a separate top-level runtime directory.
- [x] 2.2 Add process-lifetime exclusive ownership before database open and abandoned-run recovery, with safe stale-descriptor recovery and existing-owner diagnostics.
- [x] 2.3 Extend additive health metadata with service release, protocol, lifecycle identity, canonical data-directory identity, PID/start time, and active-work summary without exposing secrets.
- [x] 2.4 Add process-level tests proving that a second service cannot open or recover the same data directory, stale state is recoverable, PID reuse cannot authorize signaling, and a different data directory remains independently usable.

## 3. Race-Safe Launcher and Development Entries

- [x] 3.1 Replace the CLI-owned child abstraction with a user-scoped service resolver that captures the canonical invocation directory before service resolution and keeps workspace and service cwd independent.
- [x] 3.2 Implement atomic concurrent startup coordination so one contender starts a detached service and losing contenders wait for authenticated health instead of failing on the winning port bind.
- [x] 3.3 Add explicit development server resolution using an absolute source-project path or executable and construct `uv run --project <absolute-root> typed-code serve` as an argument array without shell interpolation.
- [x] 3.4 Add one-time development link/configuration commands and documentation so the linked `typed-code` command and the direct `uv --project` service command both run while the shell remains in an unrelated target workspace.
- [x] 3.5 Cover concurrent cold start, stale development path, unrelated port occupant, unauthorized token, incompatible protocol/release, legacy unmanaged service, explicit external service, and absent backend with focused launcher tests.
- [x] 3.6 Exercise the linked CLI and direct `uv` service from at least two temporary target directories outside the source tree, including a non-Git directory, and verify each persisted session uses the invocation directory rather than the source or service cwd.

## 4. Persistent Service and Multi-Client Semantics

- [x] 4.1 Detach service stdio and process-group lifetime from the initiating CLI, persist bounded logs under `${data_dir}/runtime`, and remove automatic service termination from normal TUI shutdown.
- [x] 4.2 Keep the service persistent by default while adding an optional disabled-by-default idle policy whose shutdown guard checks active runs, pending approvals, and connected event streams.
- [x] 4.3 Ensure conflicting operations from two clients resolve through existing authoritative phase/revision transitions and structured conflicts followed by snapshot/event reconciliation.
- [x] 4.4 Add process-level scenarios for two simultaneous CLI startups, two workspaces on one service, two observers on one session, initiating-CLI exit during a run, second-client continuity, completed-run replay, and approval continuity.

## 5. Service Management and Security Boundary

- [x] 5.1 Add `typed-code server status`, `start`, `stop`, `restart`, and `logs` dispatch before TUI startup, with idempotent start and status that never starts an absent service.
- [x] 5.2 Add authenticated graceful shutdown/restart control that refuses ordinary operations while any run or approval is active and requires a separate explicit force path with affected-session diagnostics.
- [x] 5.3 Redact bearer/provider credentials from descriptors, lifecycle output, failure messages, and logs; retain loopback-only binding and reject descriptors whose identity does not match authenticated health.
- [x] 5.4 Reserve and test the future same-origin browser authentication boundary, including Host/Origin rejection and a browser-scoped credential interface that cannot return the long-lived CLI bearer token, without shipping Web assets or enabling broad CORS.
- [x] 5.5 Cover absent, healthy, stale, incompatible, active-work-blocked, forced, and unresponsive service management behavior through command-level and real-process tests.

## 6. macOS Production Distribution

- [x] 6.1 Create the selected `@typed-code/server-darwin-arm64` package containing the self-contained companion and pin it as a same-version platform dependency of `@typed-code/cli`.
- [x] 6.2 Rename the public npm bin to `typed-code`, remove the `typed-code-cli` entry, resolve only the matching packaged companion in production, and emit actionable detected-platform diagnostics when no verified companion exists.
- [x] 6.3 Build reproducible macOS companion and npm tarballs in release CI with checks for executable mode, checksums, package contents, CLI/service version identity, and protocol compatibility.
- [x] 6.4 Install the packed tarballs on a clean Apple Silicon macOS host, launch from an unrelated non-repository directory without Python or `uv`, configure credentials, create a session, stream assistant/thinking/tool output, exit the initiating CLI, resume from a second CLI, and safely stop the service.
- [x] 6.5 Run and record one controlled live-provider smoke before claiming macOS production support; retain deterministic controlled-provider coverage for ordinary CI.

## 7. Cutover and Quality Gates

- [x] 7.1 Update help, onboarding, install, development, upgrade, troubleshooting, service-management, unsupported-platform, breaking-command, backup, and runtime-cleanup documentation while preserving XDG credentials and database migration guidance.
- [x] 7.2 Regenerate public OpenAPI/SDK artifacts for additive health or administration contracts and run the Python, SDK, CLI, contract-drift, lint, type-check, build, and unit-test gates.
- [x] 7.3 Perform real-terminal validation of ordinary `typed-code` startup, multiple simultaneous CLIs, active-run client exit/reconnect, service commands, explicit external service mode, and terminal cleanup from workspaces outside the source tree.
- [x] 7.4 Validate the OpenSpec change strictly and record macOS artifact evidence, remaining unverified platforms, selected freezer/trust decisions, startup/resource measurements, and any deferred Web implementation boundary before release.
