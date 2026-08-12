## MODIFIED Requirements

### Requirement: Streaming terminal presentation
The CLI SHALL render the shared ordered run timeline through stable pi-tui components for normalized user messages, incrementally updated Markdown assistant messages, thinking, named tool lifecycle, tool results, approvals, compaction, notices, errors, and terminal outcomes. Streaming SHALL preserve component identity, incomplete-Markdown renderability, manual scroll intent, draft input, selection, and focus.

#### Scenario: Receive text deltas
- **WHEN** assistant text deltas arrive for one message id
- **THEN** the CLI updates one existing pi-tui Markdown component and completion retains its identity instead of replacing it or duplicating prior text

#### Scenario: Receive incomplete streaming Markdown
- **WHEN** an in-flight response temporarily ends inside a code fence, list, table, or emphasis delimiter
- **THEN** the transcript remains renderable and later deltas complete the same block without resetting the viewport

#### Scenario: Receive tool lifecycle events
- **WHEN** a tool starts, updates, and completes, fails, or is denied
- **THEN** one stable tool row preserves its name, updates its bounded summary and status marker, and retains the terminal result in the timeline

#### Scenario: Preserve manual scroll position
- **WHEN** the user scrolls away from the transcript end while new output arrives
- **THEN** the ScrollView remains anchored, shows a new-output indicator, and returns to follow mode only after an explicit jump to latest

#### Scenario: Follow output at transcript end
- **WHEN** new streamed content arrives while the transcript ScrollView is following its end
- **THEN** the viewport follows the newest content and does not show an unseen-output indicator

#### Scenario: Terminal is resized
- **WHEN** terminal dimensions change during streaming, editing, or a focused workflow
- **THEN** the CLI reflows keyed components while preserving session state, draft input, focus, overlay state, and manual scroll intent

### Requirement: Status presentation of context budget
The CLI status area SHALL show provider-confirmed input, output, and total tokens against the active model's declared context budget. It SHALL distinguish last-confirmed values from current-turn pending usage, visualize context pressure at available widths, and never present character counts as tokens.

#### Scenario: Status reflects selected model budget
- **WHEN** confirmed usage is available for a selected model with a 272000-token budget and terminal width permits
- **THEN** the footer shows confirmed input, output, total, 272000 budget, percentage, and whether the values belong to the completed turn

#### Scenario: Narrow terminal prioritizes usage risk
- **WHEN** terminal width is constrained
- **THEN** the footer retains agent/approval priority and a compact total-versus-budget indicator while omitting lower-priority input/output detail

#### Scenario: A turn is in progress
- **WHEN** a later turn is active before its usage event arrives
- **THEN** the previous confirmed usage remains visible with a pending label rather than being reset to zero

#### Scenario: Usage is unavailable
- **WHEN** the model budget is known but the provider has not reported usage
- **THEN** the footer shows the known budget and an unavailable confirmed-usage value rather than zero

### Requirement: Responsive terminal workspace
The CLI SHALL use pi-tui's alternate-screen layout with a fixed identity header, independently scrollable timeline, live activity row, multiline editor, and status footer. Focused secondary workflows SHALL use opaque overlays or full-height replacement panels selected by available dimensions, and terminal resizing SHALL preserve session state, draft text, scroll intent, overlay state, and focus.

#### Scenario: Open the interactive workspace
- **WHEN** startup, service negotiation, and required setup complete
- **THEN** header, timeline, activity, editor, connection, model, workspace, and confirmed usage occupy distinct readable regions with the editor focused

#### Scenario: Open a secondary workflow
- **WHEN** the user opens help, configuration, model selection, session recovery, status, diagnostics, thinking inspection, approval detail, theme, or key guidance
- **THEN** the CLI uses a bounded opaque pi-tui surface, keeps active output readable where dimensions allow, and restores focus to the prior usable component when closed

#### Scenario: Resize to a short terminal
- **WHEN** the terminal cannot show every secondary region
- **THEN** the layout preserves active approval controls, activity, and composer; collapses or omits decorative and low-priority detail; and does not render beyond the viewport

#### Scenario: Use a narrow terminal
- **WHEN** terminal width cannot fit complete header, activity, and usage detail on single rows
- **THEN** the layout prioritizes composer, active approval or run state, selected model, connection, and compact context risk while truncating or omitting lower-priority detail

### Requirement: Observable terminal agent activity
The CLI SHALL continuously derive the shared agent activity independently from SSE connection state and render a textual state plus a platform-appropriate pi-tui loader or stable marker. The activity row SHALL name an active or approval-gated tool and show a bounded current summary when available.

#### Scenario: Thinking streams
- **WHEN** thinking deltas are active and no approval or tool call has higher priority
- **THEN** the activity row reports Thinking and the timeline updates the active thinking block

#### Scenario: Named tool runs
- **WHEN** a tool lifecycle event identifies `bash` as active
- **THEN** the activity row reports Calling bash with a bounded summary while the matching timeline item updates in place

#### Scenario: Connection recovers during activity
- **WHEN** SSE reconnects while the last known activity is responding
- **THEN** the CLI simultaneously reports Reconnecting and Responding without inferring run termination

### Requirement: Discoverable terminal actions and slash commands
The CLI SHALL generate slash names, aliases, descriptions, argument hints, state availability, autocomplete, help, and execution from the shared typed action catalog. The supported surface SHALL include help, model/reasoning selection, configuration, new session, current/all-workspace resume, status, manual compaction, transcript copy/export, theme, diagnostics, abort, key guidance, approval, and clean quit actions where applicable. Slash text SHALL never be sent as a model turn.

#### Scenario: Complete a command name
- **WHEN** the user types `/` or a partial slash command in the editor
- **THEN** pi-tui autocomplete lists matching available and unavailable commands with descriptions, availability reasons, and insertion behavior without submitting the editor

#### Scenario: Complete command arguments
- **WHEN** a command accepts model, reasoning, provider, session, workspace, theme, export, or approval arguments
- **THEN** completion supplies context-appropriate values at the cursor and does not expose credentials or hidden server tokens

#### Scenario: Invoke manual compaction while busy
- **WHEN** the user invokes `/compact` during an active run or pending approval
- **THEN** the action is refused with its idle-state requirement and no compaction request is sent

#### Scenario: Export could overwrite a file
- **WHEN** `/export` targets an existing path
- **THEN** the CLI requires an explicit overwrite decision and never includes credentials or collapsed reasoning by default

#### Scenario: Unknown command is submitted
- **WHEN** the user submits an unrecognized slash command
- **THEN** the CLI leaves session state unchanged, shows a concise error, and points to completion or `/help` without contacting the model

## ADDED Requirements

### Requirement: Terminal Markdown ergonomics
The CLI SHALL define a coherent pi-tui Markdown theme for headings, lists, blockquotes, tables, inline code, code fences, and links; visually separate user prompts from assistant output; and keep raw terminal control sequences from model output inert. Completed responses SHALL not retain a streaming cursor.

#### Scenario: Render a code fence
- **WHEN** assistant Markdown contains a fenced code block
- **THEN** the CLI shows its language label when present, preserves indentation, wraps or clips according to the documented terminal policy, and offers transcript copy without injecting escape sequences

#### Scenario: Render an unsafe control sequence
- **WHEN** model or tool text contains terminal control bytes or untrusted OSC content
- **THEN** the CLI strips or renders it inert before pi-tui output

### Requirement: Terminal thinking inspection
Active thinking SHALL remain visible as subdued streamed activity. Completed thinking SHALL collapse to a one-line item, and a focused newest-first selector SHALL let the user expand, jump to, copy, and collapse a specific item without changing authoritative session state.

#### Scenario: Inspect one of several thinking items
- **WHEN** multiple completed thinking items exist and the user invokes the thinking action
- **THEN** a pi-tui selector identifies each by recency and preview, choosing one scrolls to and expands exactly that item, and closing restores prior focus

### Requirement: Terminal-local display preferences
The CLI SHALL expose a theme/display workflow supporting automatic capability detection plus documented low-color and no-color modes. Display preference changes SHALL preview immediately, persist outside the service-owned shared model settings, and remain reversible.

#### Scenario: Preview a theme
- **WHEN** the user changes theme or density in the display overlay
- **THEN** visible components update through pi-tui invalidation without losing transcript, draft, scroll, or focus and cancellation restores the prior preference

### Requirement: Terminal approval priority
A pending approval SHALL remain reachable and readable even in a narrow terminal or while the user has scrolled away. Approval controls SHALL show the named tool and server-provided summary, require a deliberate approve/reject key path, and preserve unsent editor text.

#### Scenario: Approval arrives off-screen
- **WHEN** an approval arrives while the user inspects earlier transcript content
- **THEN** the activity/status regions show the pending tool and a direct approval action without forcing the timeline to its end
