## Purpose

Defines the server-authoritative session, persistence, command, snapshot, and event-stream behavior shared by the MVP CLI and future independent clients.

## ADDED Requirements

### Requirement: Versioned service contract
The service SHALL expose versioned JSON command resources and versioned event envelopes whose public fields are independent of provider and agent-framework SDK types.

#### Scenario: Supported protocol version
- **WHEN** a client sends a request using a supported protocol version
- **THEN** the service validates the request and returns a response in that version

#### Scenario: Unsupported protocol version
- **WHEN** a client requests an unsupported protocol version
- **THEN** the service rejects the request with a structured version error

### Requirement: Server-authoritative sessions
The service SHALL own session history, model selection, workspace association, run state, approvals, and transcript state; clients SHALL submit commands rather than authoritative history.

#### Scenario: Create a session
- **WHEN** a client creates a session with an allowed workspace and model
- **THEN** the service persists it and returns an authoritative session snapshot

#### Scenario: Resume a session
- **WHEN** a client requests an existing session
- **THEN** the service returns its persisted snapshot and transcript without requiring the client to resubmit history

#### Scenario: Client supplies fabricated state
- **WHEN** a client command includes fields that attempt to replace server-owned history, tool calls, or approval state
- **THEN** the service rejects those fields and does not mutate the session

### Requirement: Session and run concurrency
The service SHALL allow at most one active run per session while permitting multiple clients to observe its state.

#### Scenario: Start a run on an idle session
- **WHEN** an authorized client submits a non-empty prompt to an idle session
- **THEN** the service creates one run and transitions the session to an active phase

#### Scenario: Submit while a run is active
- **WHEN** a client submits another prompt while the session already has an active run
- **THEN** the service rejects the command with a conflict response without starting a second run

#### Scenario: Observe an active run
- **WHEN** another client subscribes to an active session
- **THEN** it can receive snapshots and events without gaining authority to replace the active run state

### Requirement: Durable local persistence
The service SHALL persist sessions, runs, model messages, approvals, snapshots, and ordered event metadata in SQLite before reporting durable state transitions to clients.

#### Scenario: Restart after a completed run
- **WHEN** the service restarts after a completed run
- **THEN** the session and completed transcript remain available

#### Scenario: Restart during an active run
- **WHEN** the service starts and finds a run that never reached a terminal state
- **THEN** it marks the run interrupted, preserves its recorded history, and exposes the session as resumable by a new turn

### Requirement: Authoritative snapshots
The service SHALL expose session snapshots with a monotonically increasing revision, current phase, selected model, workspace, active run, pending approval summary, and normalized transcript.

#### Scenario: State changes
- **WHEN** a durable session field changes
- **THEN** the service increments the revision and publishes the resulting authoritative snapshot or update

#### Scenario: Client has stale state
- **WHEN** a client reconnects with a revision older than the server revision
- **THEN** the server snapshot supersedes the client state

### Requirement: Resumable ordered events
The service SHALL assign a monotonically increasing per-session sequence number to public events and SHALL stream them over SSE.

#### Scenario: Subscribe to new events
- **WHEN** a client subscribes with the latest observed sequence number
- **THEN** the service streams only later events in sequence order

#### Scenario: Resume after disconnection
- **WHEN** a client reconnects with an earlier valid sequence number
- **THEN** the service replays retained later events and then continues with live events

#### Scenario: Requested events are no longer retained
- **WHEN** a client requests a sequence older than the retained event range
- **THEN** the service instructs the client to refresh the authoritative snapshot before continuing

### Requirement: Local-first service exposure
The MVP service SHALL bind to a loopback interface by default and SHALL keep provider credentials entirely on the server.

#### Scenario: Default startup
- **WHEN** the service starts without an explicit listen address
- **THEN** it accepts connections only through the local loopback interface

#### Scenario: Client reads configuration
- **WHEN** a client obtains model or session metadata
- **THEN** no provider credential is included in the response or event stream

### Requirement: Local configuration and credential precedence
The service SHALL load non-sensitive settings from `${XDG_CONFIG_HOME:-~/.config}/typed-code/config.toml` and secrets from `${XDG_CONFIG_HOME:-~/.config}/typed-code/credentials.toml`. A value present in either configuration file SHALL take precedence over its matching environment variable; environment variables SHALL provide fallback values only when the corresponding file value is absent.

#### Scenario: Configuration file overrides environment
- **WHEN** a supported setting or credential is present in its configuration file and a different matching environment variable is also set
- **THEN** the service uses the configuration-file value

#### Scenario: Environment provides a missing value
- **WHEN** a supported setting or credential is absent from its configuration file and its matching environment variable is set
- **THEN** the service uses the environment-variable value

#### Scenario: Separate secrets from ordinary settings
- **WHEN** the service loads local configuration
- **THEN** provider base URLs, model defaults, listen settings, Bash settings, and limits come from `config.toml`, while the typed-code server token and provider API keys come from `credentials.toml` or their fallback environment variables

#### Scenario: Credential file permissions are unsafe
- **WHEN** `credentials.toml` is accessible by group or other users
- **THEN** the service refuses to load credentials from the file and reports a secret-safe configuration error

#### Scenario: Provider credential is absent
- **WHEN** a provider API key is absent from both `credentials.toml` and its fallback environment variable
- **THEN** the service starts, reports that provider as `missing_credentials`, and rejects session creation with that provider

#### Scenario: Server token is absent
- **WHEN** the typed-code server token is absent from both `credentials.toml` and `TYPED_CODE_SERVER_TOKEN`
- **THEN** the service refuses to start authenticated API routes and reports a secret-safe configuration error

### Requirement: Structured failures
The service SHALL return stable error codes for validation, compatibility, authorization, conflict, missing resource, and internal run failures.

#### Scenario: Invalid command
- **WHEN** a client sends a command that fails schema validation
- **THEN** the service returns a validation error without changing durable session state

#### Scenario: Run failure
- **WHEN** a provider or tool causes the active run to fail
- **THEN** the service records a terminal failed state and emits a sanitized error event
