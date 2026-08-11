## Purpose

Defines the minimum interactive terminal client and reusable TypeScript service client required to operate the agent MVP without embedding server-side runtime behavior.

## ADDED Requirements

### Requirement: Thin service client
The TypeScript client SHALL communicate only through the versioned public service contract and SHALL NOT execute model requests, coding tools, or provider authentication locally.

#### Scenario: Connect to a compatible service
- **WHEN** the CLI starts with a reachable compatible service address
- **THEN** it negotiates the protocol version and loads service-owned model and session state

#### Scenario: Connect to an incompatible service
- **WHEN** the service does not support the client protocol version
- **THEN** the CLI displays a version compatibility error and does not start a session

#### Scenario: Service unavailable
- **WHEN** the configured service cannot be reached
- **THEN** the CLI displays a connection error and does not silently start an embedded agent runtime

### Requirement: Session workflows
The CLI SHALL allow users to create a session, list persisted sessions, resume a selected session, and view its authoritative transcript.

#### Scenario: Create a session
- **WHEN** the user selects an allowed workspace and available model
- **THEN** the CLI creates the session through the service and renders the returned snapshot

#### Scenario: Resume a session
- **WHEN** the user selects a persisted session
- **THEN** the CLI attaches to that session and renders the server transcript before accepting new input

### Requirement: Interactive run controls
The CLI SHALL allow the user to submit a prompt to an idle session, abort an active run, and resolve pending approvals.

#### Scenario: Submit a prompt
- **WHEN** the user submits non-empty text while the session is idle
- **THEN** the CLI sends one run command and renders the resulting streamed activity

#### Scenario: Abort a run
- **WHEN** the user invokes abort while a run is active
- **THEN** the CLI sends a cancellation command and reflects the server’s terminal cancellation state

#### Scenario: Resolve an approval
- **WHEN** the server reports a pending approval
- **THEN** the CLI presents its server-provided summary and sends the user’s approve or reject decision for that approval identifier

### Requirement: Streaming terminal presentation
The CLI SHALL render normalized user messages, assistant text, thinking activity, tool calls, tool results, approvals, errors, and session status through `pi-tui` without rendering provider SDK payloads.

#### Scenario: Receive text deltas
- **WHEN** the event stream emits assistant text deltas
- **THEN** the CLI updates the active assistant message without duplicating prior text

#### Scenario: Receive tool lifecycle events
- **WHEN** a tool starts, updates, and completes
- **THEN** the CLI updates one stable tool presentation through those states

#### Scenario: Terminal is resized
- **WHEN** terminal dimensions change during a run
- **THEN** the CLI reflows the transcript and composer without losing session state

### Requirement: Event-stream recovery
The CLI SHALL retain the last processed event sequence and use it to resume after a transient SSE disconnection.

#### Scenario: Recover retained events
- **WHEN** the event stream reconnects and the server retains all missing events
- **THEN** the CLI processes each missing event once in sequence order and resumes live rendering

#### Scenario: Recovery requires a snapshot
- **WHEN** the missing event range is no longer retained
- **THEN** the CLI refreshes the authoritative snapshot and continues from its current sequence

### Requirement: MVP platform contract
The CLI SHALL support macOS and Linux terminals in environments where the required JavaScript runtime and Bash-backed service are available. Native Windows and PowerShell behavior SHALL NOT be claimed by the MVP.

#### Scenario: Supported terminal environment
- **WHEN** the CLI runs on a supported macOS or Linux terminal
- **THEN** interactive input, streaming rendering, resize handling, and exit cleanup operate through the documented key bindings

#### Scenario: Native Windows environment
- **WHEN** the CLI is invoked in an unsupported native Windows or PowerShell environment
- **THEN** the project makes no MVP compatibility guarantee and documentation identifies the environment as unsupported

### Requirement: Clean client shutdown
The CLI SHALL restore terminal state and release subscriptions when it exits, without cancelling a server run unless the user explicitly requested cancellation.

#### Scenario: Exit while idle
- **WHEN** the user exits an idle session
- **THEN** the CLI restores the terminal and closes its service connection

#### Scenario: Disconnect during an active run
- **WHEN** the CLI process exits or loses its connection during an active run
- **THEN** the server run remains active and can be observed after reconnecting
