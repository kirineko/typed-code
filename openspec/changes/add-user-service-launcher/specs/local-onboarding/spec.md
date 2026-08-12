## MODIFIED Requirements

### Requirement: Automatic local service lifecycle
The default interactive entry SHALL ensure that exactly one compatible authenticated loopback agent service owns a given canonical user data directory before opening the main chat UI. The default data directory SHALL identify one service regardless of client count or workspace count; only an explicitly different data directory MAY create an isolated service domain. Concurrent clients SHALL coordinate startup atomically, attach to the winning service, and recover stale runtime metadata without spawning competing services. The user-scoped service lifetime SHALL be independent of the CLI or future local Web client that first requested it, and clean client exit SHALL NOT stop that service or interrupt its active runs.

#### Scenario: No local service is running
- **WHEN** the default entry cannot reach a compatible service for the configured user data directory
- **THEN** one startup contender acquires exclusive ownership, starts the local agent service, publishes non-secret connection metadata, waits for authenticated health and protocol negotiation, and then allows all waiting clients to attach

#### Scenario: Compatible service already running
- **WHEN** a compatible authenticated loopback service already owns the configured user data directory
- **THEN** every new CLI or local Web client reuses that service and does not spawn a duplicate process

#### Scenario: Two clients start concurrently
- **WHEN** multiple clients attempt to start typed-code before the service is ready
- **THEN** exactly one service process becomes the owner and losing contenders wait for and attach to it instead of failing on a port race

#### Scenario: Exit after spawning service
- **WHEN** the client that caused the user-scoped service to start exits cleanly
- **THEN** the client releases its subscriptions and terminal while the service and any server-owned run remain available to other or later clients

#### Scenario: Runtime metadata is stale
- **WHEN** service metadata or a process identifier remains after the owning service has exited
- **THEN** the next startup validates ownership, safely replaces the stale metadata, and starts one replacement service without deleting persistent sessions

#### Scenario: Second service targets the same data directory
- **WHEN** another service process attempts to own a data directory that already has a live owner
- **THEN** it refuses startup before recovering sessions or accepting API traffic and identifies the existing service through non-secret diagnostics

## ADDED Requirements

### Requirement: Safe user-scoped service shutdown
The user-scoped service SHALL remain running by default after all clients disconnect. It MAY stop itself only when an explicit idle policy is configured and the documented interval expires with no active run, pending approval, or connected client. Explicit ordinary stop or restart operations SHALL be refused while a run or approval is active unless the user supplies a deliberate force action whose interruption consequences are shown.

#### Scenario: Default service remains resident
- **WHEN** all clients disconnect and no idle policy was explicitly configured
- **THEN** the user-scoped service remains available until an explicit lifecycle operation, process failure, user logout, system shutdown, or upgrade replacement

#### Scenario: Idle service expires
- **WHEN** the service has no active run, pending approval, or connected client for the configured idle interval
- **THEN** it closes persistent resources, removes its runtime ownership metadata, and exits cleanly

#### Scenario: Agent continues after CLI exit
- **WHEN** the last CLI disconnects while a server-owned run is still active
- **THEN** the service remains running, completes or pauses that run according to its normal state machine, and retains events for later replay

#### Scenario: Ordinary stop during an active run
- **WHEN** the user requests an ordinary service stop or restart while any session has an active run or pending approval
- **THEN** the operation is refused with the affected session state and does not cancel or abandon the run

### Requirement: Shared local client boundary
The user-scoped service SHALL support multiple authenticated local clients over the same versioned HTTP and event-stream contracts. Client-specific disconnection SHALL NOT change authoritative session state, and conflicting commands from two clients SHALL resolve through server-authoritative success or structured conflict followed by state reconciliation.

#### Scenario: CLI clients use different workspaces
- **WHEN** two CLI clients connected to the same service create sessions from different canonical working directories
- **THEN** each session retains its own workspace and tool execution is scoped to that session rather than the service process working directory

#### Scenario: Two clients observe one session
- **WHEN** two authenticated clients are attached to the same session
- **THEN** both can replay and receive the same durable events while only server-accepted commands change session state

#### Scenario: Clients submit conflicting commands
- **WHEN** two clients attempt incompatible state transitions for the same session revision
- **THEN** one authoritative transition succeeds and the other receives a structured conflict suitable for immediate snapshot reconciliation

### Requirement: Runtime state is colocated with user data
The service SHALL store its disposable lifecycle lock, non-secret descriptor, and bounded logs under `${data_dir}/runtime` and SHALL NOT introduce a separate top-level runtime directory. Runtime contents SHALL NOT be the sole source of persistent session state and SHALL be safely reconstructible while the service is stopped.

#### Scenario: Initialize the default data directory
- **WHEN** the service first initializes the default user data directory
- **THEN** it keeps `typed-code.db` at the data-directory root and creates an owner-only `runtime` child for service lifecycle files

#### Scenario: Runtime contents are stale or removed
- **WHEN** runtime files survive a crash or are removed while no service owns the data directory
- **THEN** the next startup validates lock ownership and authenticated health, reconstructs the disposable files, and preserves all durable sessions

#### Scenario: Two workspaces share default storage
- **WHEN** CLI clients launched from different canonical workspaces use the same default data directory
- **THEN** they attach to one service and store both sessions in the same database with distinct session workspace paths

### Requirement: Future Web authentication boundary
A future browser client SHALL be able to share the user-scoped service without receiving or persisting the long-lived CLI bearer token. Production browser traffic SHALL use a same-origin or equivalently constrained bootstrap mechanism, and adding broad unauthenticated cross-origin access SHALL NOT be required by the service lifecycle.

#### Scenario: Local Web client is introduced
- **WHEN** a future Web entry opens against the running user-scoped service
- **THEN** it can establish a browser-scoped authenticated session without exposing the credentials-file bearer token to application JavaScript or browser storage

#### Scenario: Untrusted cross-origin request
- **WHEN** a browser origin that was not authorized attempts to invoke protected service APIs
- **THEN** the service rejects the request without changing sessions, configuration, or workspace state
