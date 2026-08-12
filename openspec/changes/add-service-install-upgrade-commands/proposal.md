## Why

The new user-scoped launcher can run a packaged companion, but service acquisition and replacement are still tied to how the CLI itself was installed or to an absolute development source path. Users need an explicit, inspectable command path that installs, verifies, upgrades, rolls back, and removes the service without entering the source checkout or weakening singleton/data-safety guarantees.

## What Changes

- Add a non-TUI `typed-code service` command family for `install`, `check`, `upgrade`, `rollback`, `status`, and `uninstall`; retain `typed-code server` for runtime start/stop/restart/log operations.
- Add a user-owned immutable service version store and one atomic active-version record, separate from durable session data and disposable runtime identity.
- Resolve official platform artifacts from a release channel, verify registry integrity, project checksums, platform/release/protocol identity, executable mode, and macOS trust before activation.
- Make install and upgrade transactional: stage and preflight a candidate, respect active-run/approval guards, stop the old service, switch atomically, start and health-check the candidate, and automatically restore the prior version if activation fails.
- Keep the CLI/service compatibility boundary explicit. A service command SHALL install only a release declared compatible with the running CLI; when a newer CLI is required it reports the exact package-manager action instead of creating a partially upgraded installation.
- Add rollback and uninstall safety around database migrations, retained versions, credentials, session data, runtime cleanup, and explicit destructive purge confirmation.
- Make ordinary startup diagnose an absent, stale, or incompatible managed installation and offer the exact recovery command; development source/executable overrides remain explicit and never mutate the production service store.
- Add deterministic offline/local-artifact inputs for CI and air-gapped installation while keeping network release discovery opt-in and testable.
- This change depends on the completed `add-user-service-launcher` lifecycle, identity, management, and Darwin ARM64 distribution contracts.

## Capabilities

### New Capabilities
- `service-installation`: Command-driven service discovery, verified installation, transactional activation, upgrade, rollback, and removal.

### Modified Capabilities
- `local-distribution`: Production service resolution changes from package-local companion execution to an explicitly managed, versioned service installation with verified fallback/bootstrap inputs.
- `local-onboarding`: Startup and first-run guidance gain actionable install/upgrade recovery without requiring a source-project configuration.

## Impact

- Affected TypeScript areas: CLI command dispatch, service lifecycle resolution, release metadata/download verification, managed version store, terminal progress/error presentation, and command-level/process tests.
- Affected Python areas: additive compatibility/preflight metadata, migration compatibility reporting, and shutdown/activation health checks; agent execution semantics remain unchanged.
- Affected release assets: signed release manifest, per-platform artifact checksums/integrity, retention metadata, and CI publication ordering.
- Affected contracts: additive service compatibility/install metadata in health or a dedicated preflight command; no browser API is introduced.
- Persistent data risk: activation must never modify credentials or sessions before a candidate passes artifact preflight, and rollback must be blocked when the database is not backward-compatible with the retained service.
- Platform scope: Darwin ARM64 is the first production source; unsupported targets remain explicit until their own signed artifact and clean-host evidence exist.
