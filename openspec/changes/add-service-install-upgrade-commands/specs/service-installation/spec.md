## Purpose

Defines a command-driven, verified, and recoverable lifecycle for acquiring and activating the local agent service independently of a source checkout.

## ADDED Requirements

### Requirement: Installation commands are distinct from runtime commands
The CLI SHALL expose a non-interactive `typed-code service` command family for installation state and artifact lifecycle while retaining `typed-code server` for running-process lifecycle. Installation commands SHALL work before the TUI starts and SHALL return stable nonzero exit codes for unavailable updates, invalid artifacts, active-work conflicts, and activation failures.

#### Scenario: Inspect installation without starting a service
- **WHEN** the user runs `typed-code service status` or `typed-code service check`
- **THEN** the command reports the installed version, active version, compatible available version, platform, source/channel, and verification state without starting a service or modifying files

#### Scenario: Runtime command remains separate
- **WHEN** the user runs `typed-code server status`
- **THEN** it reports running-process state and does not download, install, activate, or delete a service version

### Requirement: Service artifacts are verified before installation
The installer SHALL accept only an artifact whose platform, architecture, release identity, protocol compatibility, executable mode, registry integrity, project checksum, and platform trust evidence match authenticated release metadata. Verification SHALL finish in a staging location before the artifact can become active.

#### Scenario: Install a valid official artifact
- **WHEN** the selected channel provides a compatible artifact whose metadata, checksum, executable identity, and macOS trust assessment all pass
- **THEN** the installer places it in an immutable version directory and records its verified source without executing an unverified path

#### Scenario: Artifact verification fails
- **WHEN** any digest, identity, platform, protocol, permission, signature, notarization, or release-metadata check fails
- **THEN** installation fails without changing the active version, running service, credentials, sessions, or database

#### Scenario: Platform has no verified artifact
- **WHEN** install or upgrade runs on an unsupported operating-system and architecture pair
- **THEN** it reports the detected target and verified targets and does not fall back to a source checkout, `PATH`, or an unrelated executable

### Requirement: Activation is transactional and singleton-safe
Install, upgrade, and rollback SHALL serialize through one installation lock per canonical data domain. Activation SHALL preflight the candidate, enforce the existing active-run and pending-approval shutdown guard, stop the current managed service, atomically select the candidate, start it, and require authenticated identity and health before declaring success.

#### Scenario: Concurrent install and upgrade
- **WHEN** two service mutation commands run concurrently for the same installation domain
- **THEN** one owns the transaction and the other waits or exits with a deterministic busy result without corrupting staged, installed, or active-version state

#### Scenario: Active work blocks activation
- **WHEN** an ordinary install, upgrade, rollback, or uninstall would replace or stop a service with an active run or pending approval
- **THEN** the operation is refused with affected-session diagnostics unless the documented explicit force action is supplied

#### Scenario: Candidate fails after active switch
- **WHEN** the candidate cannot start or fails authenticated release/protocol/health validation after selection
- **THEN** the installer restores the previous active record, restarts the previous compatible service when safe, and reports both the original activation failure and rollback outcome

#### Scenario: Client disconnects during activation
- **WHEN** the invoking terminal exits after the transaction has begun
- **THEN** the transaction reaches one durable terminal state—old active, new active, or explicitly recoverable failed state—rather than leaving a partial pointer or writable version directory

### Requirement: Upgrade respects CLI compatibility and release channels
The upgrade resolver SHALL select only an official service release declared compatible with the installed CLI and configured channel. It SHALL NOT activate a service requiring a newer CLI, a different protocol major, or an unsupported data schema.

#### Scenario: Compatible update is available
- **WHEN** the selected channel offers a newer verified service compatible with the current CLI and database
- **THEN** `service check` reports it and `service upgrade` can activate it transactionally

#### Scenario: Newer product release requires a CLI update
- **WHEN** the newest service cannot be used by the current CLI
- **THEN** the command leaves the installation unchanged and reports the required CLI version and exact supported package-manager upgrade action

#### Scenario: No update is available
- **WHEN** the active verified service is the newest compatible release on the selected channel
- **THEN** `service upgrade` exits successfully as an idempotent no-op and reports that state

### Requirement: Rollback is data-compatible
The installer SHALL retain a bounded number of prior verified versions and SHALL permit rollback only when the target declares compatibility with the current durable database schema. Artifact rollback SHALL NOT restore or overwrite credentials, sessions, transcripts, or workspace files.

#### Scenario: Prior service is compatible
- **WHEN** a retained verified prior version supports the current database schema
- **THEN** `service rollback` activates it through the same guarded transaction and preserves durable data

#### Scenario: Migration prevents rollback
- **WHEN** the database has crossed a schema boundary unsupported by the retained service
- **THEN** rollback is refused before stopping the active service and reports the required backup/restore or forward-upgrade recovery path

### Requirement: Uninstall preserves user data by default
`typed-code service uninstall` SHALL stop and remove managed service binaries and installation metadata but SHALL preserve configuration, credentials, and durable session data by default. Destructive data purge SHALL require a separate explicit confirmation that names every removed root.

#### Scenario: Ordinary uninstall
- **WHEN** the service is idle and the user runs `typed-code service uninstall`
- **THEN** managed versions and their active record are removed, runtime metadata is cleaned after shutdown, and XDG credentials and `typed-code.db` remain intact

#### Scenario: Purge is not explicitly confirmed
- **WHEN** a command requests durable-data removal without the documented non-interactive confirmation
- **THEN** it refuses without deleting service versions, credentials, sessions, or runtime state

### Requirement: Offline installation uses the same verifier
The installer SHALL accept an explicit local release manifest and artifact for deterministic CI, air-gapped operation, and recovery. Local inputs SHALL pass the same identity, checksum, compatibility, permission, and platform trust checks as network inputs.

#### Scenario: Valid local artifact
- **WHEN** the user supplies a compatible official manifest and artifact from local paths
- **THEN** installation succeeds without network access and records the local source and verified release identity

#### Scenario: Local artifact is modified
- **WHEN** a local artifact no longer matches its manifest or trust evidence
- **THEN** it is rejected before installation and no network fallback occurs unless the user explicitly requests one
