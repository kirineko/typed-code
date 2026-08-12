## Purpose

Defines first-run local setup, automatic server-token and process lifecycle for ordinary users, and the in-session configuration slash-command contracts that keep provider credentials easy to manage without exposing service plumbing.
## Requirements
### Requirement: Single local entry without manual server tokens
The default interactive entry SHALL start a usable local coding session without requiring the user to supply a server bearer token or service base URL. The system SHALL generate and persist a server token under the XDG credentials file when absent, and SHALL use that token for local service authentication automatically.

#### Scenario: First launch with no credentials file
- **WHEN** a user starts the default interactive entry and no XDG credentials file exists
- **THEN** the system creates the configuration directory with mode `0700`, creates `credentials.toml` with mode `0600` containing a generated server token, and does not print that token in the interactive UI

#### Scenario: Subsequent launch reuses stored server token
- **WHEN** a user starts the default interactive entry and a valid server token already exists in credentials
- **THEN** the client authenticates with that token without prompting the user for a token flag

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

### Requirement: First-run provider key onboarding
On startup the system SHALL determine whether any provider credential is present among the supported providers. If none are present, the CLI SHALL run a blocking `pi-tui` setup workflow that collects at least one provider key, writes it to `credentials.toml` with mode `0600`, reloads service configuration, and confirms provider availability before enabling a new-session draft. If any provider key is present, the system SHALL skip mandatory key onboarding while keeping the same configuration workflow available in-session.

#### Scenario: No provider keys configured
- **WHEN** the user starts the default entry and no supported provider credential is configured
- **THEN** the TUI guides the user to choose a provider, enter a secret key without echo, save it securely, and validate provider availability before enabling the composer

#### Scenario: At least one provider key exists
- **WHEN** the user starts the default entry and at least one supported provider key is already configured
- **THEN** the system skips mandatory key onboarding even if other providers remain unavailable

#### Scenario: Onboarding writes safe permissions
- **WHEN** onboarding creates or updates `credentials.toml`
- **THEN** the file is a current-user-owned regular file with mode `0600` and the configuration directory remains mode `0700`

#### Scenario: Onboarding reload fails
- **WHEN** a provider key is saved but the running service rejects or times out while reloading configuration
- **THEN** the setup workflow reports the secret-safe failure, keeps the configuration workflow available for correction or retry, and does not expose the entered key

### Requirement: Slash command configuration surface
The interactive CLI SHALL intercept composer input that begins with `/` as a local command and SHALL NOT submit those lines as model prompts. `/config` SHALL open the same TUI-owned provider configuration workflow used for first-run onboarding, and configuration commands containing credentials SHALL NOT be retained in composer history or rendered in the transcript.

#### Scenario: Slash input is not a model turn
- **WHEN** the user submits a line that starts with `/` while the command is available
- **THEN** the CLI handles it locally and does not create a server turn for that line

#### Scenario: Configuration secrets are not entered as arguments
- **WHEN** the user attempts to include a provider key in `/config` command arguments
- **THEN** the CLI refuses the argument, opens or directs the user to secret input, and does not retain or render the supplied value

#### Scenario: Unknown slash command
- **WHEN** the user submits an unrecognized slash command
- **THEN** the CLI shows a short error and directs the user to command completion or help without contacting the model

### Requirement: Config menu for providers and keys
The `/config` command SHALL open a focused configuration interface that allows the user to view provider availability, set or replace supported provider API keys through secret input, save changes to the XDG credential and config files, and request a hot reload of the running local service. The interface SHALL share behavior with first-run setup, SHALL never display stored secret values, and SHALL remain usable after validation or reload failures.

#### Scenario: Open provider configuration
- **WHEN** the user invokes `/config`
- **THEN** the CLI displays supported providers and whether each is available or missing credentials without displaying stored API key values

#### Scenario: Replace a provider key
- **WHEN** the user sets a new provider key through the secret configuration workflow and saves
- **THEN** the key is written to `credentials.toml` and the running service reloads credentials so subsequent model listing and runs observe the new availability state

#### Scenario: Server token remains hidden in config UI
- **WHEN** the user opens `/config` or first-run setup
- **THEN** the UI does not display the raw server bearer token value

#### Scenario: Cancel configuration
- **WHEN** the user cancels configuration before saving
- **THEN** the CLI leaves persisted credentials and active service configuration unchanged and restores focus to the prior usable interface

#### Scenario: Reload validation fails
- **WHEN** saved configuration cannot be activated because reload validation fails
- **THEN** the CLI displays a secret-safe structured error, preserves the previously active service configuration, and allows the user to correct or retry the configuration workflow

### Requirement: Hot reload safety
When a configuration reload is requested, the service SHALL validate the new credential file permissions and contents before replacing the in-memory credential set. If the new configuration is unsafe or invalid, the service SHALL reject the reload, retain the previously loaded credentials, and return a structured error suitable for display in the CLI.

#### Scenario: Unsafe credentials file on reload
- **WHEN** a reload is requested and the credentials file has unsafe permissions
- **THEN** the service keeps the previous credentials active and reports a secret-safe configuration error

#### Scenario: Successful reload
- **WHEN** a reload is requested with a valid credentials file
- **THEN** provider availability in health and model listing updates without requiring a process restart

### Requirement: Credential-aware model and reasoning defaults
The system SHALL select an available startup model in this precedence order: explicit CLI override, most recently successful `/model` selection, DeepSeek when `deepseek-v4-flash` is available, configured service default, then the first available model. A successful interactive model and reasoning-effort selection SHALL be persisted as a non-secret local preference and restored on the next launch when that exact provider/model remains available. DeepSeek SHALL expose `none`, `low`, `high`, and `max` with `high` as its default effort. OpenAI reasoning models SHALL expose `none`, `low`, `medium`, `high`, `xhigh`, and `max` with `medium` as their default effort. Models without declared reasoning support SHALL receive no inferred reasoning setting.

#### Scenario: Both provider credentials are configured without a remembered model
- **WHEN** DeepSeek and CLIProxy credentials are configured, both providers have available models, and no explicit or remembered model exists
- **THEN** the new-session draft selects `deepseek/deepseek-v4-flash`

#### Scenario: Restore the most recently selected model
- **WHEN** the user successfully selects an available model through `/model` and starts the CLI again without an explicit model override
- **THEN** the new-session draft restores that exact provider/model even when DeepSeek is also available

#### Scenario: Remembered model is unavailable
- **WHEN** the persisted provider/model is no longer available and no explicit model override is supplied
- **THEN** the CLI ignores the stale preference and selects the next available model according to the normal precedence

#### Scenario: Use provider-specific reasoning defaults
- **WHEN** the selected DeepSeek model has no remembered effort
- **THEN** the CLI selects `high`
- **WHEN** the selected OpenAI reasoning model has no remembered effort
- **THEN** the CLI selects `medium`

#### Scenario: Selected model lacks declared reasoning support
- **WHEN** a selected model profile does not declare configurable reasoning
- **THEN** the runtime omits the reasoning setting rather than assuming support

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
