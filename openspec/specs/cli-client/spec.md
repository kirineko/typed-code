## Purpose

Defines the minimum interactive terminal client and reusable TypeScript service client required to operate the agent MVP without embedding server-side runtime behavior.

## Requirements

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


### Requirement: Default entry hides service plumbing
The default interactive CLI entry SHALL NOT require `--token` or an explicit base URL for ordinary local use when XDG credentials already contain (or can generate) a server token. Advanced flags for base URL and token MAY remain available for power users but SHALL NOT be required in the default documented path.

#### Scenario: Launch without token flag
- **WHEN** the user starts the default CLI entry without `--token` and a server token exists or can be generated under XDG credentials
- **THEN** the CLI proceeds with local authentication using the stored token

#### Scenario: Advanced explicit token still works
- **WHEN** the user supplies an explicit token flag or environment override for the server token
- **THEN** the CLI uses that token for the session according to documented precedence

### Requirement: Model selection slash command
The `/model` command SHALL present available models from the service catalog, including provider, model identifier, availability, and each model’s context token budget. While the current session is idle, selecting a model SHALL switch the current session’s provider and model through the service. While a run is active, `/model` SHALL refuse to switch and SHALL explain that the session must be idle.

#### Scenario: Switch model while idle
- **WHEN** the user runs `/model`, the session phase is idle, and the user selects an available model
- **THEN** the service updates the session’s provider and model, the CLI refreshes from the authoritative snapshot, and subsequent turns use the selected model

#### Scenario: Refuse switch while running
- **WHEN** the user runs `/model` while a run is active or the session is awaiting approval
- **THEN** the CLI does not change the session model and shows that the session must be idle

#### Scenario: Show context budgets in the picker
- **WHEN** the model picker is displayed
- **THEN** each listed model includes its configured maximum context length used for budgeting

### Requirement: Status presentation of context budget
The CLI status presentation SHALL surface approximate context usage against the **currently selected model’s** context token budget when usage information is available.

#### Scenario: Status reflects selected model budget
- **WHEN** the session uses a model whose context budget is 272000 tokens and usage is known
- **THEN** the status presentation compares usage to that 272000 budget rather than a global constant shared by all models