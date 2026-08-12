## MODIFIED Requirements

### Requirement: Clean client shutdown
The CLI SHALL restore terminal state and release its subscriptions when it exits, without stopping the user-scoped service or cancelling a server-owned run unless the user explicitly requested the corresponding destructive action.

#### Scenario: Exit while idle
- **WHEN** the user exits an idle session
- **THEN** the CLI restores the terminal and closes its service connection without terminating the shared local service

#### Scenario: Disconnect during an active run
- **WHEN** the CLI process exits or loses its connection during an active run
- **THEN** the server run remains active and can be observed after reconnecting from that or another client

### Requirement: Default entry hides service plumbing
The default `typed-code` interactive entry SHALL NOT require `--token`, an explicit base URL, a backend source-project path, or a separately launched service for ordinary local use. Advanced connection flags MAY remain available for power users, but the default installed path SHALL resolve and authenticate the compatible user-scoped service automatically.

#### Scenario: Launch without token flag
- **WHEN** the user invokes `typed-code` without token, base URL, or service-executable flags and a server token exists or can be generated under XDG credentials
- **THEN** the CLI resolves or starts the compatible user-scoped service and authenticates with the stored token

#### Scenario: Advanced explicit token still works
- **WHEN** the user explicitly supplies a base URL and token for an externally managed compatible service
- **THEN** the CLI connects according to documented precedence without attempting to own or stop that service

## ADDED Requirements

### Requirement: Invocation directory is the default workspace
The CLI SHALL capture the canonical absolute path of the directory from which `typed-code` is invoked and use it as the default launch workspace. Resolving or starting the backend SHALL NOT replace that workspace with the CLI installation directory, the typed-code source directory, or the service process working directory.

#### Scenario: Invoke from a project directory
- **WHEN** the user changes to `/work/project-a` and runs `typed-code` without `--workspace`
- **THEN** the new draft and any subsequently created session use the canonical absolute identity of `/work/project-a`

#### Scenario: Explicit workspace override
- **WHEN** the user supplies a valid explicit workspace path
- **THEN** the CLI uses the canonical override according to documented precedence while service resolution remains independent of both directories

#### Scenario: Working directory is invalidated during startup
- **WHEN** the invocation directory cannot be resolved or becomes unavailable before session creation
- **THEN** startup fails with the affected path and does not silently substitute the installation or home directory

### Requirement: Local service management surface
The `typed-code` command SHALL expose status, start, stop, restart, and log-discovery operations for the user-scoped service. These operations SHALL report service identity, protocol compatibility, lifecycle state, and safe shutdown blockers without displaying bearer tokens or provider credentials.

#### Scenario: Inspect running service
- **WHEN** the user requests service status while a compatible service is running
- **THEN** the command reports non-secret endpoint, process, version, protocol, uptime, and active-work summary

#### Scenario: Inspect absent service
- **WHEN** the user requests service status and no live owner exists
- **THEN** the command distinguishes an absent service from stale runtime metadata and exits without starting the service

#### Scenario: View service logs
- **WHEN** the user requests service logs
- **THEN** the command identifies or reads the user-scoped log destination while redacting authentication and provider secrets

### Requirement: Multiple CLI clients remain usable
Multiple CLI processes SHALL be able to connect to the same user-scoped service concurrently. Loss or exit of one client SHALL NOT terminate service availability for the others, and each client SHALL surface reconnecting, conflict, and authoritative session updates independently.

#### Scenario: First CLI exits before second CLI
- **WHEN** two CLI clients are connected and the one that originally requested service startup exits
- **THEN** the other CLI remains connected or reconnects to the same service without losing its authoritative session state

#### Scenario: Reattach after a completed background run
- **WHEN** a CLI exits during a run and later resumes the session after the service completed it
- **THEN** event replay and the authoritative snapshot reconstruct the completed assistant, thinking, tool, approval, and usage state
