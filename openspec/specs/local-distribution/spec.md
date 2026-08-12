## Purpose

Define how typed-code is installed or linked once and then launched from any target working directory without depending on a source checkout in that directory, with production feasibility proven first on macOS.

## Requirements

### Requirement: Installed command is independent of the target workspace
The production installation SHALL provide a `typed-code` command that can start from any readable directory, use that invocation directory as the default workspace, and resolve its compatible local service runtime without requiring the target directory to contain typed-code source files, `pyproject.toml`, or `package.json`. The ordinary production path SHALL NOT require a separately installed Python interpreter or `uv`.

#### Scenario: Launch from an unrelated project
- **WHEN** a user installs typed-code, changes to a project directory that does not contain the typed-code source tree, and runs `typed-code`
- **THEN** the CLI opens a draft whose canonical workspace is that project directory and reaches a compatible local service

#### Scenario: Launch from a non-repository directory
- **WHEN** a user runs `typed-code` from a readable directory that is not a Git repository
- **THEN** the directory is accepted as the workspace without requiring repository metadata

#### Scenario: Production runtime dependency is absent
- **WHEN** the installed production command is run on a supported platform without user-installed Python or `uv`
- **THEN** it uses its packaged service runtime rather than failing because those development tools are absent

### Requirement: Development entries work from the target working directory
The documented development setup SHALL make both the linked CLI entry and the `uv`-managed service entry invocable while the shell remains in an arbitrary target workspace. Development service resolution SHALL use an explicit absolute source-project location or configured development executable and SHALL NOT discover the typed-code backend by walking upward from the target workspace.

#### Scenario: Run the linked CLI from another project
- **WHEN** a developer completes the documented one-time link and development-service configuration, changes to another project, and invokes `typed-code`
- **THEN** the CLI uses that project as the workspace while resolving the backend from the configured typed-code source environment

#### Scenario: Run the uv service from another project
- **WHEN** a developer invokes the documented `uv` service command while the shell is in a target workspace outside the typed-code repository
- **THEN** the command resolves the typed-code Python project through an explicit absolute project path and starts the same development service without changing the target workspace

#### Scenario: Development source path is stale
- **WHEN** the configured typed-code source project or development server executable no longer exists
- **THEN** startup fails with a diagnostic that identifies the stale development configuration and does not fall back to interpreting the target workspace as the backend project

### Requirement: macOS-first production companion proof
Before production installation support is claimed, the release process SHALL build and exercise a self-contained macOS service companion together with the published CLI entry. The first required production target SHALL be macOS on Apple Silicon; other operating-system and architecture combinations SHALL report their unverified or unsupported status explicitly until equivalent release evidence exists.

#### Scenario: Fresh macOS Apple Silicon installation
- **WHEN** the production package is installed in a clean macOS Apple Silicon environment that has the declared Node.js runtime but no typed-code source checkout, Python, or `uv`
- **THEN** `typed-code` starts from an unrelated workspace, launches or attaches to the packaged service, negotiates the expected protocol, creates a session, streams a real response, and shuts down according to the user-scoped service policy

#### Scenario: Unsupported production platform
- **WHEN** the production package is invoked on a platform for which no compatible companion was installed or verified
- **THEN** it fails before opening the TUI with the detected platform, architecture, supported targets, and an actionable installation message

### Requirement: CLI and service versions are matched
The installed CLI SHALL select a companion service built for the same release and SHALL verify protocol compatibility before creating a session. It SHALL NOT silently run an incompatible companion found elsewhere on `PATH`.

#### Scenario: Packaged companion is compatible
- **WHEN** the installed CLI resolves its packaged companion and the service reports the expected protocol
- **THEN** startup continues without requiring the user to select a service executable

#### Scenario: Existing service is incompatible
- **WHEN** a user-scoped service is reachable but reports an incompatible protocol or release identity
- **THEN** the CLI refuses to create a session and provides a safe restart or reinstall action rather than starting a second service over the same data directory
