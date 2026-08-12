## 1. Release Trust and Artifact Gate

- [ ] 1.1 Define and validate the signed `service-manifest.v1` schema, canonical serialization, Ed25519 key ids, expiry, channel, CLI/protocol/schema compatibility, and target artifact fields.
- [ ] 1.2 Build a signed, notarized, stapled Darwin ARM64 DMG containing only the companion and receipt; verify attach/copy, Developer ID identity, Gatekeeper assessment, and clean-host offline use.
- [ ] 1.3 Add protected release-environment manifest signing, canonical GitHub Releases publication ordering, key-rotation fixture generation, and checks that unsigned or partially published releases are never discoverable.
- [ ] 1.4 Record artifact size, mount/copy time, first install time, online/offline Gatekeeper behavior, signing-key recovery procedure, and the explicit go/no-go result before enabling network install.

## 2. Compatibility Contract

- [ ] 2.1 Add service and database schema compatibility models to the Python protocol and additive authenticated health response.
- [ ] 2.2 Implement `typed-code-server compatibility --data-dir <path> --json` with read-only SQLite inspection and no ownership, migration, recovery, bind, provider, or credential side effects.
- [ ] 2.3 Extend SDK types and contract exports for release, protocol, readable-schema range, write target, and migration-required state.
- [ ] 2.4 Cover empty, current, older-readable, migration-required, newer-unreadable, corrupt, locked, and symlinked data-directory compatibility probes.

## 3. Managed Version Store and Verifier

- [ ] 3.1 Implement canonical `${data_dir}/service` paths, owner-only staging, exclusive install lock, immutable version directories, receipts, active selection, and atomic synchronized writes.
- [ ] 3.2 Implement strict manifest parsing, canonical signature verification, pinned-key rotation, approved-origin/redirect rules, expiry/clock handling, and stable structured errors.
- [ ] 3.3 Implement bounded streaming download and DMG/local-artifact verification for digest, size, mount options, member allowlist, path safety, executable mode, package/receipt identity, codesign, team requirement, and Gatekeeper.
- [ ] 3.4 Implement installed-version inventory, bounded retention, staging cleanup, and garbage collection that preserves active and transaction-referenced versions.
- [ ] 3.5 Add adversarial tests for tampered manifests/artifacts, unknown/rotated keys, redirects, truncation, expansion limits, traversal, links, wrong platform/release/protocol/schema, unsafe permissions, and concurrent store mutation.

## 4. Service Command Surface

- [ ] 4.1 Add pre-TUI `typed-code service status` and `check` dispatch, human and JSON output, stable exit semantics, channel selection, and no-start/no-download guarantees.
- [ ] 4.2 Add `service install` resolution for verified package bootstrap, signed network manifest, exact version, and explicit offline manifest/artifact inputs without implicit fallback.
- [ ] 4.3 Add `service upgrade` compatibility selection, idempotent no-update behavior, CLI-update diagnostics, preview opt-in, and explicit non-interactive confirmation flags.
- [ ] 4.4 Add `service rollback` target selection and database-readable-range refusal without restoring durable data.
- [ ] 4.5 Add conservative `service uninstall` and separately confirmed purge with canonical-root, symlink, live-owner, filesystem-root, and home-directory guards.
- [ ] 4.6 Add help/completion entries and command-level tests proving `service` artifact actions remain distinct from `server` process actions.

## 5. Transactional Activation and Recovery

- [ ] 5.1 Implement the durable activation journal and phase transition invariants under the per-domain install lock.
- [ ] 5.2 Implement candidate preflight, active-work/approval guard reuse, affected-session force diagnostics, and clean old-service shutdown.
- [ ] 5.3 Implement free-space calculation, the 1 GiB interactive confirmation threshold, non-interactive `--yes`, closed-database backup, synchronization, and pre-mutation failure behavior.
- [ ] 5.4 Implement atomic candidate selection, managed startup, authenticated receipt/health matching, commit, and prior-version retention.
- [ ] 5.5 Implement failed-activation termination by authenticated identity, pre-migration database restore, old-selection restore, old-service restart, and combined failure diagnostics.
- [ ] 5.6 Implement next-invocation transaction recovery for interruption at every durable phase without trusting a descriptor PID alone.
- [ ] 5.7 Add kill-point process tests across download, verification, backup, shutdown, selection, candidate start, health, rollback, and commit; assert one recoverable active version and SQLite integrity after every case.

## 6. Launcher and Onboarding Cutover

- [ ] 6.1 Change production resolution to the active verified managed receipt while preserving explicit development project/executable and external `--no-spawn` precedence.
- [ ] 6.2 Add one-time migration from the same-release package-local companion through explicit `service install`, with no silent startup mutation.
- [ ] 6.3 Add focused startup recovery for absent, outdated, tampered, transaction-incomplete, and CLI-incompatible installations with exact copyable commands.
- [ ] 6.4 Order first-run service installation before provider onboarding while preserving existing credentials across cancel, offline selection, verification failure, and retry.
- [ ] 6.5 Cover two concurrent first starts, multiple workspaces/data domains, active-run upgrade deferral, initiating-client exit, explicit development override, and external-service behavior in real processes.

## 7. Release, Documentation, and Quality Gates

- [ ] 7.1 Update install, upgrade, rollback, channel, offline, backup, migration, uninstall, purge, trust, unsupported-platform, recovery, automation/JSON, and development documentation.
- [ ] 7.2 Regenerate OpenAPI/SDK contracts and run Python, SDK, CLI, contract-drift, lint, type-check, build, and deterministic unit/process test gates.
- [ ] 7.3 Build two identical unsigned fixture releases, verify deterministic manifests/checksums, then execute the protected signed/notarized release path without repacking the accepted executable.
- [ ] 7.4 Install from the published stable channel on a clean Apple Silicon host, upgrade from the previous release, exercise a migration and failed-candidate rollback, verify session continuity, then uninstall while preserving data.
- [ ] 7.5 Validate an offline stapled-DMG install with network disabled and no Python, `uv`, npm companion, or source checkout.
- [ ] 7.6 Strictly validate the OpenSpec change and record verified platforms, artifact/startup/resource measurements, trust-root decisions, migration/rollback evidence, and remaining release blockers.
