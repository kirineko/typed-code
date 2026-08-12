## Context

The completed predecessor change establishes one detached service owner per canonical data directory, authenticated health identity, guarded shutdown, a Darwin ARM64 companion package, and explicit development overrides. Production resolution still executes the companion found beside the installed npm CLI, while development resolution executes an absolute source project or binary. There is no durable installation catalog, release-channel resolver, transaction journal, or safe way to replace a running service from a command.

The service owns SQLite and migrations. The Node CLI owns user interaction and process discovery but cannot safely copy a live SQLite database or decide downgrade compatibility from version strings alone. A replacement protocol therefore needs artifact metadata before execution and database schema metadata from both the active and candidate services.

## Goals / Non-Goals

**Goals:**

- Install and replace the production service from any workspace through explicit commands.
- Verify every byte and compatibility claim before it becomes executable or active.
- Preserve singleton ownership, active-work guards, XDG credentials, and durable sessions.
- Make interruption and failed activation recover to a deterministic version.
- Keep development overrides independent from production installation state.
- Support deterministic local artifacts for CI and offline recovery.

**Non-Goals:**

- Self-update the globally installed npm CLI or invoke an unknown package manager automatically.
- Add background update daemons, silent startup downloads, forced updates, or telemetry.
- Support an unverified operating system merely because an executable URL exists.
- Roll back user data across an incompatible migration or silently restore an old database snapshot after normal post-upgrade use.
- Change provider configuration, agent semantics, Web authentication, or TUI session behavior.

## Decisions

### 1. Separate artifact lifecycle from process lifecycle

The public command split is:

```text
typed-code service status
typed-code service check [--channel stable|preview]
typed-code service install [--version V | --manifest PATH --artifact PATH]
typed-code service upgrade [--version V] [--force]
typed-code service rollback [--to V] [--force]
typed-code service uninstall [--force] [--purge --confirm <data-root>]

typed-code server status|start|stop|restart|logs
```

`service` mutates installed artifacts and the active selection. `server` mutates or inspects only the current process. Both dispatch before pi-tui initialization. `service status` combines installation and running identity but never starts or downloads anything; `service check` may fetch signed metadata but never downloads an artifact. A successful check returns exit code `0` whether or not an update exists; `--json` exposes `update_available`, selected version, and compatibility details for automation, while fetch/verification failures remain nonzero.

The existing packaged companion becomes a bootstrap source. `service install` may copy it into the managed store after applying the same verifier. Ordinary startup never silently materializes or upgrades a managed installation. This makes every binary mutation attributable to a command and keeps startup latency predictable.

### 2. Use an immutable per-data-domain version store

Each canonical data directory owns its service installation domain:

```text
${data_dir}/
├── typed-code.db
├── runtime/                         # live lock, descriptor, bounded logs
└── service/
    ├── active.json                  # atomic non-secret selection
    ├── transaction.json             # present only during mutation/recovery
    ├── install.lock                 # serializes service mutations
    ├── staging/<nonce>/             # mode 0700, never executable by launcher
    └── versions/<release>/<target>/
        ├── typed-code-server         # mode 0755, immutable after verification
        └── receipt.json              # digest, source, compatibility, trust result
```

A custom data directory intentionally creates an isolated service and installation domain, matching existing ownership semantics. The extra companion disk cost is preferable to cross-domain reference counting and ambiguous rollback ownership.

`active.json`, `receipt.json`, and `transaction.json` contain no tokens or provider secrets. All writes use create-exclusive staging, file and directory synchronization, and atomic rename. Installed version directories are never modified in place. Garbage collection retains the active release, the configured number of verified predecessors (default two), and any version referenced by an incomplete transaction.

### 3. Publish a signed release manifest with a pinned trust root

Release CI publishes `service-manifest.v1.json`, a detached Ed25519 signature, and platform artifacts to the project's canonical GitHub Releases origin only after platform signing/notarization succeeds. The signing key is held in a protected release environment, is unavailable to pull-request jobs, and is identified by a non-secret key id. The CLI embeds accepted manifest public keys and verifies the signature with Node's built-in crypto before trusting fields. A manifest entry includes:

- service release and channel;
- target OS/architecture and archive URL/size;
- SHA-256 and registry integrity when distributed through npm;
- protocol major and supported CLI release range;
- readable database schema range and write target;
- executable relative path and mode;
- macOS signing team/designated requirement;
- publication and optional expiry timestamps.

Key rotation uses an overlap period: an older trusted key signs a manifest containing the next key id, and at least one CLI release embeds both. An unknown key, expired metadata, downgrade below channel policy, redirect to an unapproved origin, oversized response, or HTTP-to-HTTPS downgrade is a hard failure.

For Darwin ARM64, the canonical network and offline artifact is a signed, notarized, and stapled read-only DMG containing the companion plus release receipt. Verification is layered: manifest signature, bounded streaming download, artifact digest, DMG attach with `nobrowse`/read-only options, member allowlist, executable version/compatibility output, Developer ID team/designated-requirement match, `codesign --verify --deep --strict`, and `spctl --assess --type execute`. The existing npm companion may bootstrap an online install only when Gatekeeper can validate its notarization; it is not the offline trust container. Future targets must define equivalent platform trust checks before entering the manifest's verified-target set.

### 4. Add a side-effect-free candidate compatibility command

A candidate must be interrogated before it can open the production database:

```text
typed-code-server compatibility --data-dir <canonical-path> --json
```

It opens SQLite read-only, does not acquire service ownership, run migrations, recover sessions, bind a port, or load provider credentials. It reports executable release/protocol identity, current database schema, readable schema range, target schema, and whether starting would migrate.

The active service exposes the same schema fields in authenticated health. The installer requires candidate output, signed manifest claims, npm package version, and current CLI expectations to agree. This prevents a version label from authorizing an unsafe database open.

### 5. Execute activation as a recoverable journaled transaction

One command holds `service/install.lock` through these durable phases:

```text
resolved -> downloaded -> verified -> prepared -> old-stopped
         -> selected -> candidate-started -> committed
                         |
                         +-> rollback-selected -> rollback-started -> failed
```

Before `old-stopped`, cancellation deletes staging and leaves the service untouched. `prepared` records active/target releases, canonical roots, schema decision, and whether a pre-migration database backup is required. Ordinary replacement calls the authenticated shutdown endpoint and honors active-run/approval blockers. `--force` uses the existing explicit interruption contract and prints affected sessions before proceeding.

If a migration backup would exceed 1 GiB, interactive activation requires confirmation after showing database size, required temporary space, and free space. Non-interactive activation requires `--yes`. Regardless of size, the transaction aborts before shutdown unless free space exceeds the artifact staging requirement plus twice the closed database size and the configured safety margin.

After clean shutdown, if the candidate would migrate, the installer copies the closed SQLite database to a transaction-scoped backup and synchronizes it before selecting the candidate. No client can attach to the candidate until authenticated health matches the target receipt. If startup or health fails, the installer terminates only the process whose authenticated identity matches the transaction, restores the pre-migration database backup when one was taken, atomically restores the old selection, and starts the old service. Because the candidate was never declared healthy, no accepted user work can be lost by this automatic restore.

On process interruption, the next service mutation or ordinary startup reads `transaction.json` under the lock and completes rollback or commit from the last durable phase. It never guesses from PID alone. A terminal result preserves diagnostics and removes the journal only after active selection, database state, and authenticated running identity agree.

### 6. Treat later rollback differently from activation rollback

A user-requested rollback after successful use never restores the activation backup. It is allowed only when the retained binary's declared readable schema range contains the current database schema. If not, the command leaves the current service running and explains that a user-selected external backup restore or forward upgrade is required.

This preserves all sessions created after upgrade and avoids pretending executable rollback is equivalent to data rollback. Backups created for activation failure are short-lived transaction artifacts, not a general backup product.

### 7. Keep CLI and service updates coordinated but not self-modifying

The configured channel defaults to `stable`; `preview` is explicit. The resolver selects the newest service whose manifest declares compatibility with the currently executing CLI, protocol major, target platform, and data schema. A newer incompatible product release is reported with the required CLI version and a copyable `npm install --global @typed-code/cli@<version>` command. The CLI never executes that command itself.

After the user updates the CLI, `typed-code service upgrade` installs and activates its compatible service. Startup detects the old active service and presents this exact action. This cleanly handles lockstep releases without asking a running executable to replace its own global installation.

### 8. Offline input is explicit and non-fallback

`--manifest <path> --artifact <path>` disables network discovery. The local manifest must carry a valid trusted signature and identify exactly that artifact; all normal extraction, trust, compatibility, and transaction checks still apply. Test fixtures use a test trust root injected through internal APIs, never a production command-line bypass. If local verification fails, the command stops rather than silently switching to the network.

### 9. Uninstall is conservative

Ordinary uninstall uses the same active-work guard, stops the managed process, removes the active record and managed version tree, and reconstructs/cleans runtime metadata only after ownership ends. It retains `typed-code.db`, configuration, credentials, preferences, and logs needed for diagnosis.

`--purge` is a separate destructive path. In non-interactive use it requires `--confirm` equal to the canonical data root and prints every root before deletion. It refuses symlinks, filesystem root/home, mismatched canonical paths, and a live owner. Development executables and source directories are never deleted.

## Risks / Trade-offs

- **Trust-root rotation can strand old CLIs.** Use overlapping keys, manifest versioning, expiry with clock-skew tolerance, and a documented CLI-upgrade recovery path.
- **Stapled DMG increases release and install complexity.** It is selected because the current npm tarball cannot carry stapled notarization evidence for a fully offline Gatekeeper check; keep DMG mount/copy logic macOS-specific and gated by clean-host measurements.
- **Crash recovery spans files, processes, and SQLite.** Keep a small explicit transaction state machine, synchronize every irreversible boundary, and test kill points rather than relying on broad exception cleanup.
- **Pre-migration backups temporarily double database storage.** Check free space before shutdown, bound retention, and abort before mutation when capacity is insufficient.
- **Per-data-directory binaries duplicate storage.** This preserves isolation and simple ownership; cross-domain content-addressed deduplication is deferred until measurements justify it.
- **Exact CLI compatibility limits independent service updates.** Signed compatibility ranges may widen for patch releases, but the installer must never infer compatibility from semver alone.
- **Archive extraction adds attack surface.** Allowlist members, reject absolute/traversal/link entries, bound count and expanded size, and extract only into an owner-only staging directory.

## Migration Plan

1. Land compatibility metadata and the side-effect-free candidate command while package-local resolution remains authoritative.
2. Add the managed store and offline bootstrap install from the currently packaged companion; validate install/status/uninstall without network discovery.
3. Add journaled activation, pre-migration backup, failure rollback, retained-version rollback, and kill-point process tests.
4. Publish and verify signed release manifests in CI, then enable `check` and network `install/upgrade` for Darwin ARM64.
5. Change production startup to require the active managed installation and provide an explicit one-time migration command for existing package-local users.
6. Remove ordinary package-local execution only after packed-install, upgrade, rollback, active-work, offline, corrupted-artifact, and clean-host Gatekeeper scenarios pass.
