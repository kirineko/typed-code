## Why

The CLI currently owns a repository-relative `uv run typed-code serve` child, so concurrent clients race during startup, the owning CLI can disconnect every other client when it exits, and an installed CLI cannot reliably launch from an arbitrary working directory. A user-scoped service and cwd-independent distribution path are required before adding a Web client, while production packaging feasibility should first be proven on macOS.

## What Changes

- Replace CLI-owned child lifetime with one authenticated, loopback, user-scoped service per data directory that can be shared by multiple CLI clients and a future local Web client.
- Add atomic service discovery and startup coordination, stale-runtime recovery, protocol/version checks, idle shutdown rules, and explicit service status/start/stop/restart/log access.
- Keep active runs server-owned when a CLI exits; refuse ordinary service shutdown while runs or approvals remain active.
- Make the installed `typed-code` command treat its invocation directory as the canonical workspace and launch its companion service without depending on a repository checkout, the target directory, `uv`, or a user-managed Python installation.
- Add a production feasibility spike and release proof for a self-contained macOS server companion, starting with Apple Silicon and recording unsupported platform behavior explicitly rather than claiming unverified support.
- Add a development launcher path in which both `typed-code` and the `uv`-managed service can be invoked from any target working directory while resolving the service project through an absolute repository path or configured development server executable.
- Reserve a same-origin Web hosting/authentication boundary so a future Web UI can share the singleton service without receiving the long-lived CLI bearer token; Web UI implementation is not part of this change.
- **BREAKING**: the ordinary CLI command becomes `typed-code`, and clean CLI exit no longer stops a service merely because that CLI started it.

## Capabilities

### New Capabilities
- `local-distribution`: Cwd-independent installed and development launchers, macOS companion packaging feasibility, version matching, and unsupported-platform diagnostics.

### Modified Capabilities
- `local-onboarding`: Replace the CLI-owned local service process with an atomically started user-scoped singleton whose lifetime is independent of any one client.
- `cli-client`: Define arbitrary-directory workspace launch, server-owned run continuity, service management behavior, and the macOS-first production support claim.

## Impact

- CLI lifecycle and command entry: `packages/cli/src/bin.ts`, `packages/cli/src/config.ts`, `packages/cli/src/app.ts`, and `packages/cli/src/service-lifecycle.ts`.
- Python service startup, runtime locking, shutdown policy, health metadata, and Web authentication boundary under `src/typed_code/`.
- npm package metadata, platform-specific release artifacts, CI release jobs, and installation documentation.
- The existing XDG data directory gains a disposable `runtime/` child containing the non-secret service descriptor, lock, and bounded logs; no additional top-level runtime directory is introduced, and existing credentials and SQLite locations remain unchanged.
- Existing public HTTP/SSE contracts remain the client boundary; health/service metadata may require additive protocol fields.
- Development tooling gains a globally invocable linked CLI and an explicit absolute-path service resolver; target workspaces remain independent of the typed-code source checkout.
