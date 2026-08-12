## Context

See `proposal.md` for motivation. The current TypeScript CLI probes a fixed loopback URL, spawns `uv run typed-code serve` in the invocation directory when unreachable, marks that child as owned, and terminates it when the CLI exits. The Python service combines durable SQLite state with process-local run tasks and event publication, so two service processes cannot safely share one data directory even though SQLite uses WAL. Production currently has no artifact that carries the Python backend with the npm CLI.

The design must preserve the invocation directory as session workspace while service resolution may use an installation directory or source checkout elsewhere. Existing XDG credentials and data are user-scoped and remain the persistence boundary. The future Web client needs the same service and protocol, but browser UI implementation is deferred.

## Goals / Non-Goals

**Goals:**

- Guarantee one live service owner per canonical user data directory under concurrent startup.
- Decouple service and active-run lifetime from any CLI process.
- Make `typed-code` usable from any readable target directory in both linked development and installed production modes.
- Prove a self-contained production companion on macOS Apple Silicon before expanding the release matrix.
- Preserve existing credentials, database, HTTP/SSE contracts, and per-session canonical workspaces.
- Define a browser-safe, same-origin authentication boundary that a later Web UI can adopt.
- Provide inspectable lifecycle commands and deterministic diagnostics for stale state, incompatible versions, unsupported platforms, and unsafe shutdown.

**Non-Goals:**

- Implement the Web UI or remote/network service exposure.
- Claim Linux production packaging until an equivalent clean-host proof is completed; source development on Linux remains possible.
- Port the Python runtime to TypeScript.
- Add multi-user or cloud tenancy.
- Introduce collaborative editing or permanent session ownership by a particular client.
- Automatically reload the Python service on source changes while an Agent run is active.

## Decisions

### 1. The service is a user-scoped singleton keyed by canonical data directory

A service process, not a launcher, holds an exclusive OS file lock for its entire lifetime. On macOS and the existing Unix MVP this can use an advisory lock with owner metadata; the abstraction must leave room for a different platform implementation later. The lock key is the canonical `data_dir`: the ordinary default profile therefore has one service regardless of client or workspace count, while an explicitly different data directory forms an intentionally isolated service domain. Workspace paths never participate in service identity.

Runtime files are consolidated under a disposable child of the existing data directory rather than a separate XDG runtime root:

```text
${data_dir}/
├── typed-code.db
└── runtime/
    ├── service.lock       exclusive ownership primitive
    ├── service.json       atomic, non-secret connection/version descriptor
    └── server.log         bounded/rotated service diagnostics
```

The data directory and its `runtime/` child use owner-only permissions. `service.json` contains PID, loopback base URL, service release, protocol version, canonical data-directory identity, and start time; it never contains bearer or provider credentials. The service writes it through a temporary file plus atomic rename only after binding its endpoint and building application state. Runtime contents may survive crashes or reboot but are always disposable and reconstructible: the lock plus authenticated health establishes liveness, not descriptor or PID presence alone.

A second service targeting the same canonical data directory must acquire `${data_dir}/runtime/service.lock` before opening SQLite or calling abandoned-run recovery. Failure to acquire the lock terminates that process with existing-owner diagnostics. This ordering prevents a losing process from mutating another process's active sessions, while clients launched from any number of workspaces continue to share the same owner and database.

Alternatives rejected:

- A PID file alone has race and PID-reuse failures.
- Letting several processes rely on SQLite WAL does not share process-local `SessionManager` tasks or `EventBus` events and makes startup recovery unsafe.
- A client reference count makes service correctness depend on crash-prone UI cleanup.

### 2. All clients use one race-safe ensure-service algorithm

The launcher algorithm is:

```text
canonicalize data_dir and capture invocation cwd
        |
read descriptor + authenticated health/version probe
        | healthy
        +---------------------------------> attach
        |
        | absent/stale
        v
attempt startup coordination lock
        | winner                         | loser
        v                                v
spawn detached companion                wait for descriptor/health
        |                                |
        +-------------- ready -----------+
                         |
                       attach
```

The startup coordination lock and the service lifetime lock may be the same lock with an explicit handoff protocol, or separate locks if the spike proves handoff unreliable across Node and Python. The invariant is observable: one winner; every loser waits and re-probes rather than treating the winning process's port bind as its own failure.

The configured loopback endpoint remains authoritative. If an unrelated process occupies it, startup fails with endpoint diagnostics; it does not silently choose another port or create another database owner. A healthy service with missing singleton identity is treated as a legacy/unmanaged service and must be stopped or upgraded before the new launcher proceeds.

### 3. The service is detached and uses safe idle shutdown

The production companion is spawned outside the CLI process group, with stdin detached and stdout/stderr directed to the user-scoped log. Closing a CLI only closes its SSE/HTTP subscriptions and restores terminal state.

The service is persistent by default and exits only through an explicit lifecycle operation, process failure, user logout/system shutdown, or upgrade replacement. It still tracks authenticated API activity, active SSE connections, active runs, and pending approvals so an optional configured idle timeout can be enabled later without weakening the rule that active runs and approvals always suppress idle exit.

Ordinary `stop` and `restart` call an authenticated administrative shutdown endpoint and are refused when runs or approvals are active. A separate explicit force operation may interrupt them after presenting affected session identifiers. Process signaling is reserved for stale/unresponsive service recovery and explicit force behavior.

### 4. `typed-code` is the only user-facing CLI entry

The npm package exposes `typed-code`; the existing `typed-code-cli` entry is removed as a clean breaking cutover. At process start the CLI captures and canonicalizes `process.cwd()` before resolving any service executable. That value remains the default workspace sent through the public session contract.

Service startup receives the canonical data directory and derives all runtime state from `${data_dir}/runtime`; it must not infer service identity or workspace from its own cwd. Workspace tools continue to receive the authoritative absolute path stored on each session. A missing or deleted invocation directory is an error rather than a fallback to the package, source, home, data, or service directory.

Advanced `--workspace`, `--base-url`, `--token`, and externally managed `--no-spawn` behavior remains available with documented precedence.

### 5. Production uses a PyInstaller macOS companion package

The intended npm structure is:

```text
@typed-code/cli
  optional dependency -> @typed-code/server-darwin-arm64
                           bin/typed-code-server
```

The CLI package and companion package use the same release version. The launcher resolves only the package selected for `process.platform`/`process.arch`; it does not silently search `PATH` in production. Protocol and release identity are checked against a running singleton before session creation.

The macOS spike selected PyInstaller after comparing it with Nuitka against the actual dependency graph. PyInstaller produced the smaller artifact, built substantially faster, used less initial service memory, and preserved the HTTPS provider-error path; Nuitka changed that path into `RuntimeError: No active exception to reraise` and is rejected. The PyInstaller build explicitly collects Pydantic AI and `tiktoken`, recursive package metadata, TLS certificates, and SQLite migration assets. The selected artifact must still pass packed-install validation on a clean Apple Silicon macOS host with Node.js but without Python, `uv`, or a typed-code checkout.

The feasibility gate includes:

1. Build the companion reproducibly in release CI.
2. Install a packed npm CLI plus companion tarball, not a workspace link.
3. Launch from an unrelated non-repository directory.
4. Create and persist a session against a controlled provider endpoint, stream assistant/thinking/tool events, exit the initiating CLI, and resume from a second CLI.
5. Exercise a controlled live-provider smoke before the first public release.
6. Inspect binary dependency resolution, certificate loading, executable permissions, package size, startup time, and macOS signing/notarization implications.

The first public macOS companion is signed in CI with a Developer ID Application identity, including PyInstaller-collected nested Mach-O files, and submitted to Apple notarization as an archive before the exact verified executable is packed into npm. Ad-hoc signing remains sufficient only for local development: the measured artifact passes `codesign --verify` but is rejected by `spctl`. Failure of signed/notarized clean-host verification blocks production packaging but not singleton lifecycle or the development launcher; the fallback remains an explicitly versioned `uvx` preview rather than a hidden production dependency.

### 6. Development resolution is explicit and cwd-independent

Development keeps the normal source tools. A one-time documented setup links the npm CLI globally and configures an absolute typed-code source root or server executable. The launcher builds an argument array without shell parsing:

```text
uv run --project /absolute/path/to/typed-code typed-code serve ...
```

A developer may also execute that same `uv run --project ...` command directly while the shell stays in the target workspace. The target cwd is never used to discover the Python project. An explicit environment/config override has higher priority than platform companion resolution in development builds and produces a clear stale-path error if invalid.

Development and production feed the same ensure-service state machine. Tests inject the service executable/spawner rather than relying on global tools.

### 7. Service management is a non-TUI command surface

The entry dispatches `typed-code server status|start|stop|restart|logs` before opening the alternate-screen TUI. Status reads runtime metadata and performs a bounded authenticated probe; it does not start the service. Logs resolve the scoped log file and redact known credential values. Start is idempotent. Stop and restart respect active-work blockers and require a distinct force flag for interruption.

The health response gains additive service release and lifecycle identity fields. Protocol incompatibility remains a hard error. Administrative endpoints require the existing bearer token and loopback binding.

### 8. Web remains same-origin and receives a browser-scoped credential

A future production Web UI should be served by the singleton service so UI, REST, and SSE share one loopback origin. The planned `typed-code web` flow will open a short-lived one-time bootstrap URL that is redeemed for an HttpOnly, SameSite-strict browser session. The long-lived credentials-file bearer token is never returned to browser JavaScript or browser storage.

The service should validate host/origin and remain loopback-only. Development Web tooling should use a local dev-server proxy rather than broad production CORS. This change may reserve routes and authentication interfaces, but it does not ship browser assets or make the bootstrap flow publicly usable.

### 9. Multi-client writes stay server-authoritative

No client receives an exclusive durable session lease. Multiple clients may observe one session. Existing phase/revision checks decide concurrent commands: the first valid transition commits, later incompatible operations receive a structured conflict and refresh the authoritative snapshot/event sequence. This permits handoff between CLI and future Web without an unlock flow.

## Risks / Trade-offs

- **Frozen Python compatibility:** Dynamic provider/runtime imports or native `tiktoken` assets may be missed. Mitigation: make the macOS packaging spike the first production gate and exercise the installed tarball, not only the build output.
- **macOS trust behavior:** npm-delivered executables may encounter signing, quarantine, or notarization constraints. Mitigation: inspect behavior on a clean host and document/sign the chosen artifact before support is claimed.
- **Cross-language lock handoff:** Node launcher and Python service may disagree about lock lifetime. Mitigation: test concurrent cold starts and crash points as process-level scenarios; use separate startup/lifetime locks if handoff cannot be proven atomic.
- **Daemon persistence:** A user-scoped process consumes resources after all clients disconnect. Mitigation: expose clear status/stop commands, keep the idle-timeout mechanism configurable but disabled by default, and measure steady-state memory before changing the default.
- **Stale metadata and PID reuse:** Descriptor-only checks could target an unrelated process. Mitigation: require lock ownership, authenticated health, data-directory identity, and protocol/release checks before signaling or attaching.
- **Persistent runtime artifacts:** Consolidating runtime state under `data_dir` means stale descriptors and logs may enter backups. Mitigation: keep `runtime/` wholly disposable, document that backups need only durable data such as `typed-code.db`, and validate lock plus authenticated health before trusting any descriptor.
- **Port collision:** Refusing random fallback is less convenient when the configured port is occupied. It avoids ambiguous Web origins and split service identity; diagnostics must identify the conflict and configured override.
- **Development override leakage:** A stale source-root override could shadow a packaged companion. Mitigation: scope it to explicit development configuration and fail visibly rather than falling back.
- **Breaking command rename:** Existing scripts using `typed-code-cli` stop working. Mitigation: call it out in release notes and installation errors; do not leave two long-lived public entry names.
- **Future Web security:** Reserving a boundary without implementing it could later drift. Mitigation: record same-origin, token-isolation, and Origin/Host invariants in specs and require the Web change to reuse them.

## Migration Plan

1. Add lifecycle identity and single-owner enforcement to the Python service while retaining the existing database and credentials formats.
2. Add the race-safe launcher and service management commands behind development resolution; validate concurrent CLI behavior before removing child ownership.
3. Rename the Python development service executable internally if needed to avoid collision with the user-facing Node `typed-code` entry, while keeping an explicit `uv run --project` command.
4. Cut the CLI exit path over to subscription-only cleanup and require the new service identity; reject legacy unmanaged services with a stop/upgrade diagnostic.
5. Complete the macOS companion spike and only then wire the platform package into a packed npm installation.
6. Rename the public CLI bin to `typed-code`, update installation docs, and publish the breaking release.
7. Preserve XDG credentials and `typed-code.db` in place; create `${data_dir}/runtime` with owner-only permissions. Its lock, descriptor, and logs are disposable and may be deleted or recreated while the service is stopped.
8. Rollback is package-version rollback plus explicit service stop. No database downgrade should be required unless implementation discovers a schema change, which would require a separate migration decision.

## Open Questions

- Should the runtime endpoint remain the configured fixed port for the first Web-compatible release, or should a later design move same-origin Web startup to a descriptor-selected port?
