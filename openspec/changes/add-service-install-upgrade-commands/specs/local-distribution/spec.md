## MODIFIED Requirements

### Requirement: Installed command is independent of the target workspace
The production installation SHALL provide a `typed-code` command that can start from any readable directory, use that invocation directory as the default workspace, and resolve a compatible verified service from the user-managed service installation without requiring the target directory to contain typed-code source files, `pyproject.toml`, or `package.json`. The ordinary production path SHALL NOT require a separately installed Python interpreter or `uv`. A package-local companion MAY be used only as an explicit verified bootstrap input to `typed-code service install`; it SHALL NOT bypass managed installation state silently.

#### Scenario: Launch from an unrelated project with a managed service
- **WHEN** a user installs typed-code and a compatible service, changes to a project directory that does not contain the typed-code source tree, and runs `typed-code`
- **THEN** the CLI opens a draft whose canonical workspace is that project directory and attaches to or starts the active managed service

#### Scenario: Managed service is absent
- **WHEN** production startup has no compatible active managed service
- **THEN** it stops before session creation and presents the exact `typed-code service install` or recovery command without treating the target workspace as a backend source

#### Scenario: Explicit development override exists
- **WHEN** an absolute development project or executable is configured
- **THEN** startup uses that override through the development resolver and does not install, upgrade, activate, or delete production service versions

### Requirement: CLI and service compatibility is declared and enforced
The installed CLI SHALL select only an active service version whose signed release metadata declares compatibility with the CLI release, protocol major, platform, and durable data schema. Compatibility SHALL be checked before session creation and again after installation activation. The CLI SHALL NOT silently run an arbitrary companion found on `PATH` or a package-local binary that is not the active verified installation.

#### Scenario: Active managed service is compatible
- **WHEN** the active installation and authenticated health match the compatibility declaration
- **THEN** startup continues without downloading or mutating service installation state

#### Scenario: Existing service requires an upgrade
- **WHEN** a user-scoped service is reachable but its release is incompatible with the installed CLI
- **THEN** the CLI refuses session creation and reports whether `typed-code service upgrade`, a CLI package update, or explicit external-service mode is required

#### Scenario: Active record and running identity disagree
- **WHEN** the selected installation record does not match authenticated service health or executable identity
- **THEN** startup rejects the service and provides a repair path without signaling the descriptor PID or starting a competing database owner
