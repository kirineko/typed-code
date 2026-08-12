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
The CLI SHALL open an unsaved new-session draft for the canonical absolute launch workspace without prompting the user to select a historical session. It SHALL create and attach the service-owned session only when the user first submits a non-empty prompt, and it SHALL allow users to resume persisted sessions explicitly and view their authoritative transcripts.

#### Scenario: Launch into a new-session draft
- **WHEN** the user starts the ordinary interactive CLI for a valid workspace
- **THEN** the CLI opens a new-session draft for that canonical workspace without listing or automatically attaching a persisted session

#### Scenario: Exit an unused draft
- **WHEN** the user exits the CLI before submitting a non-empty prompt from the new-session draft
- **THEN** the CLI restores the terminal without creating a persisted session

#### Scenario: Create a session
- **WHEN** the user submits the first non-empty prompt from a draft with an allowed workspace and available model
- **THEN** the CLI creates the session through the service, attaches its event stream, submits exactly one turn, and renders the resulting streamed activity

#### Scenario: Session creation succeeds but turn submission fails
- **WHEN** the service creates the draft session but rejects or fails the first turn command
- **THEN** the CLI keeps the created session attached and reports the turn failure so the user can retry without creating another session

#### Scenario: Resume a session
- **WHEN** the user selects a persisted session through `/resume`
- **THEN** the CLI discards any unsaved draft, attaches the selected session, and renders the authoritative transcript before accepting new input

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
The CLI SHALL render normalized user messages, incrementally updated Markdown assistant messages, thinking activity, stable tool lifecycle presentations, tool results, approvals, errors, and session status through `pi-tui` without rendering provider SDK payloads. Streaming updates SHALL preserve stable transcript item identity and SHALL NOT force a user who has scrolled away from the end back to the latest output.

#### Scenario: Receive text deltas
- **WHEN** the event stream emits assistant text deltas
- **THEN** the CLI incrementally updates one Markdown presentation for the active assistant message without duplicating prior text or replacing the presentation when the message completes

#### Scenario: Receive incomplete streaming Markdown
- **WHEN** an in-flight assistant message contains temporarily incomplete Markdown such as an unclosed code fence
- **THEN** the CLI remains renderable and continues updating the same assistant message as later deltas arrive

#### Scenario: Receive tool lifecycle events
- **WHEN** a tool starts, updates, and completes or fails
- **THEN** the CLI updates one stable tool presentation through those states and retains its terminal outcome in the transcript

#### Scenario: Follow output at transcript end
- **WHEN** new streamed content arrives while the transcript viewport is following its end
- **THEN** the viewport continues following the newest content

#### Scenario: Preserve manual scroll position
- **WHEN** the user scrolls away from the transcript end and new streamed content arrives
- **THEN** the CLI preserves the selected scroll position and indicates that newer output is available

#### Scenario: Terminal is resized
- **WHEN** terminal dimensions change during a run
- **THEN** the CLI reflows the transcript, activity presentation, composer, and status areas without losing session state, draft input, focus, or manual scroll intent

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

### Requirement: Model selection slash command
The `/model` command SHALL present an interactive selection of models from the service catalog, including provider, model identifier, availability, and context token budget, and SHALL also support command argument completion. After selecting a model that declares configurable reasoning levels, the CLI SHALL present a second focused picker for thinking intensity using the service-declared values and provider-specific default. DeepSeek SHALL expose `none`, `low`, `high`, and `max` with `high` selected by default. OpenAI reasoning models SHALL expose `none`, `low`, `medium`, `high`, `xhigh`, and `max` with `medium` selected by default. The CLI SHALL visibly retain and persist the chosen level. In a new-session draft, selecting a model and reasoning level SHALL update the draft without creating a session. In an attached idle session, selecting them SHALL switch the service-owned session model and apply the reasoning level unchanged to subsequent turn requests. During an active run or pending approval, model switching SHALL be refused with an explanation.

#### Scenario: Select a model for a draft
- **WHEN** the user selects an available model while the CLI is in a new-session draft
- **THEN** the CLI updates the draft provider and model without creating a persisted session

#### Scenario: Switch model while idle
- **WHEN** the user runs `/model`, the attached session phase is idle, and the user selects an available model
- **THEN** the service updates the session provider and model, the CLI refreshes from the authoritative snapshot, and subsequent turns use the selected model

#### Scenario: Refuse switch while running
- **WHEN** the user runs `/model` while a run is active or the session is awaiting approval
- **THEN** the CLI does not change the session model and explains that the session must be idle

#### Scenario: Show context budgets in the picker
- **WHEN** the model picker or model argument completion is displayed
- **THEN** each listed model includes its configured maximum context length and provider availability

#### Scenario: Select thinking intensity
- **WHEN** the user selects a DeepSeek model
- **THEN** the picker offers `none`, `low`, `high`, and `max` and initially selects `high`
- **WHEN** the user selects an OpenAI reasoning model
- **THEN** the picker offers `none`, `low`, `medium`, `high`, `xhigh`, and `max` and initially selects `medium`
- **WHEN** the user confirms an effort
- **THEN** the CLI stores it with the model preference, displays it in the active workspace, and sends the exact value with subsequent turn requests
- **WHEN** the selected model declares no configurable reasoning levels
- **THEN** the CLI completes model selection without inventing or sending a reasoning level

### Requirement: Status presentation of context budget
The CLI status presentation SHALL show provider-confirmed input, output, and total context usage against the currently selected model's context token budget when usage information is available. It SHALL retain the last confirmed usage while a later turn is running and SHALL NOT present a character-based or otherwise invented count as live token usage.

#### Scenario: Status reflects selected model budget
- **WHEN** the session uses a model whose context budget is 272000 tokens and confirmed usage is known
- **THEN** the status presentation compares that usage to 272000 and identifies the confirmed input and output usage

#### Scenario: Usage is unavailable
- **WHEN** the selected model budget is known but the provider has not reported usage
- **THEN** the status presentation shows the known budget and an unavailable usage value rather than reporting zero

#### Scenario: A turn is in progress
- **WHEN** a new turn is running and the provider has not yet reported its usage
- **THEN** the status retains the previous confirmed usage and indicates that current-turn usage is not yet available

### Requirement: Responsive terminal workspace
The CLI SHALL provide a full-screen terminal workspace with a fixed identity header, independently scrollable transcript, current activity presentation, multiline composer, and status footer. Secondary workflows SHALL use opaque focused overlays docked below the fixed header so the newest transcript content remains readable, and the layout SHALL adapt to narrow and short terminals without hiding the composer or active approval controls.

#### Scenario: Open the interactive workspace
- **WHEN** startup, service negotiation, and required onboarding succeed
- **THEN** the CLI displays the transcript, composer, current activity, model, workspace, connection, and usage status in distinct readable regions

#### Scenario: Open a secondary workflow
- **WHEN** the user opens help, configuration, model selection, session recovery, status details, approval details, or key guidance
- **THEN** the CLI presents an opaque action surface below the fixed header and restores focus to the previous usable component when the overlay closes

#### Scenario: Use a narrow terminal
- **WHEN** the terminal is too narrow for the full status presentation
- **THEN** the CLI prioritizes the composer, active approval or run state, and essential model and connection information while omitting or truncating lower-priority detail

### Requirement: Observable agent activity
The CLI SHALL derive and display the current agent activity independently from the event-stream connection state. It SHALL distinguish at least preparing, thinking, calling a named tool, awaiting approval for a named tool, responding, cancelling, ready, and failed states when the normalized session view contains enough information.

#### Scenario: Thinking is streamed
- **WHEN** thinking deltas are active and no higher-priority approval or tool call is active
- **THEN** the CLI identifies the agent as thinking and updates the active thinking presentation

#### Scenario: A named tool is active
- **WHEN** a tool lifecycle event identifies an active tool
- **THEN** the CLI identifies the agent as calling that tool and updates the same tool presentation until its terminal state

#### Scenario: Assistant text is streamed
- **WHEN** assistant text deltas are active and no approval or tool call is active
- **THEN** the CLI identifies the agent as responding while updating the assistant Markdown block

#### Scenario: Connection is recovering during a run
- **WHEN** the event stream is reconnecting while the server-owned run may still be active
- **THEN** the CLI displays both the reconnecting connection state and the last known agent activity without claiming that the run was cancelled

#### Scenario: Completed thinking is retained
- **WHEN** a thinking item completes
- **THEN** the CLI retains it in a visually subordinate, collapsed presentation that the user can expand

#### Scenario: Provider-native thinking is retained
- **WHEN** a provider supplies completed reasoning in its native metadata rather than the normalized thinking content field
- **THEN** the service preserves that reasoning as the completed thinking item and `Ctrl+T` reveals its text

#### Scenario: Select and collapse completed thinking
- **WHEN** the session contains multiple completed thinking items and none is expanded
- **THEN** `Ctrl+T` opens a newest-first focused selector and choosing an item expands and scrolls to that exact item
- **WHEN** a completed thinking item is expanded
- **THEN** the next `Ctrl+T` collapses that item without opening the selector

### Requirement: Discoverable slash commands
The CLI SHALL maintain one discoverable slash-command surface that provides command names, aliases, descriptions, argument hints, availability, completion, help, and execution behavior without submitting command text as a model turn. The supported surface SHALL include help, model selection, configuration, new-session draft, current-project resume, all-project resume, status details, abort, key guidance, and clean quit operations.

#### Scenario: Complete a command name
- **WHEN** the user types `/` or a partial slash-command name in the composer
- **THEN** the CLI presents matching commands with descriptions and inserts the selected completion without submitting it

#### Scenario: Complete command arguments
- **WHEN** the active command supports model, session, provider, or workspace arguments
- **THEN** the CLI presents context-appropriate argument completions and applies the selected value at the cursor

#### Scenario: Configuration uses the shared modal surface
- **WHEN** the user invokes `/config` with or without a provider argument
- **THEN** provider selection and masked credential entry use the same framed, centered, focus-restoring modal presentation as the other slash-command workflows

#### Scenario: Invoke a command
- **WHEN** the user submits a recognized slash command that is available in the current state
- **THEN** the CLI executes the local command and does not create a model turn

#### Scenario: Invoke an unavailable command
- **WHEN** the user invokes a recognized command that is unsafe or unavailable in the current draft, run, or approval state
- **THEN** the CLI leaves session state unchanged and explains the availability constraint

#### Scenario: Invoke an unknown command
- **WHEN** the user submits an unrecognized slash command
- **THEN** the CLI shows a short error and directs the user to command completion or help without contacting the model

### Requirement: Canonical-workspace session recovery
The CLI SHALL organize session recovery by each session's canonical absolute `workspace_path`. `/resume` SHALL default to sessions whose workspace matches the canonical launch workspace, and an explicit all-project view SHALL group sessions by canonical workspace without inferring identity from Git metadata.

#### Scenario: Resume within the current project
- **WHEN** the user invokes `/resume` from a draft or attached session
- **THEN** the picker lists matching current-project sessions in descending `updated_at` order and does not mix in sessions from other workspace paths

#### Scenario: No current-project sessions exist
- **WHEN** the user invokes `/resume` and no persisted session matches the canonical launch workspace
- **THEN** the CLI reports that the project has no resumable sessions and leaves the current draft or attached session unchanged

#### Scenario: Browse all projects
- **WHEN** the user explicitly requests all-project session recovery
- **THEN** the CLI groups persisted sessions by canonical workspace path, disambiguates equal directory basenames with parent path information, and sorts sessions within each group by descending `updated_at`

#### Scenario: Start another new session
- **WHEN** the user invokes `/new` from an attached session
- **THEN** the CLI releases the attachment without cancelling a server-owned run, returns to an unsaved draft for the canonical launch workspace, and leaves the prior session persisted

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

### Requirement: Native web search presentation
The CLI SHALL present provider-hosted web search through the existing normalized tool lifecycle and activity presentation. It SHALL NOT render provider SDK objects, raw search payloads, or unrestricted source lists.

#### Scenario: Web search is active
- **WHEN** the event stream reports a `web_search` tool in a started or running state
- **THEN** the CLI identifies the agent as calling `web_search` and updates one stable tool presentation

#### Scenario: Web search completes
- **WHEN** a native web search completes or fails
- **THEN** the CLI retains the terminal tool outcome in the transcript using the server-provided sanitized summary

#### Scenario: Snapshot reconstructs a completed search
- **WHEN** the CLI refreshes from an authoritative snapshot that contains native web search transcript items
- **THEN** the CLI reconstructs the completed search presentation without requiring the original live stream

#### Scenario: Chronological thinking, search, and answer
- **WHEN** a run emits thinking, native web search, and then assistant text
- **THEN** the CLI presents those items in that order and does not move completed searches below the finished answer

#### Scenario: Web search keeps its query summary
- **WHEN** a native web search completes with a result summary
- **THEN** the stable tool presentation retains the sanitized query from the start event rather than replacing it with only "search completed"
