## Purpose

Defines renderer-neutral interaction, streaming, activity, usage, action, and reconciliation behavior so terminal and browser clients present the same server-authoritative agent work without duplicating business rules.

## ADDED Requirements

### Requirement: Shared authoritative client projection
Every first-party interactive client SHALL derive its session view from the same versioned snapshot and ordered event semantics. The projection SHALL preserve stable identities for messages, thinking items, tool calls, approvals, and runs, and SHALL treat a newer authoritative snapshot as superseding stale local state.

#### Scenario: Render the same active session in two clients
- **WHEN** a TUI and Web client attach to the same session and observe the same snapshot and event sequence
- **THEN** both clients expose the same transcript order, active run, pending approval, named tool status, confirmed usage, and terminal outcome despite using different renderers

#### Scenario: Event replay is reset
- **WHEN** a client reconnects after its requested event range has expired
- **THEN** it replaces the stale projection with the reset snapshot, resumes from the snapshot sequence, and does not duplicate already durable timeline items

### Requirement: Typed action catalog
First-party clients SHALL consume one typed action catalog containing stable action ids, labels, descriptions, argument definitions, current-state availability, destructive intent, and execution behavior. A renderer MAY expose an action as a slash command, command-palette item, button, menu item, or key binding, but SHALL NOT maintain a second behavior definition for that action.

#### Scenario: Action is available in different renderers
- **WHEN** `session.abort` is available for an active run
- **THEN** the TUI exposes it through `/abort` and its documented key path while the Web client exposes a contextual control and command-palette entry backed by the same action id and availability result

#### Scenario: Action is unavailable
- **WHEN** a user attempts an action whose state predicate is false
- **THEN** the client leaves authoritative state unchanged and explains the unmet condition using the action catalog's availability reason

#### Scenario: Slash-like text is ordinary Web input
- **WHEN** a Web integration chooses not to enable composer slash parsing
- **THEN** the same action remains available through the command palette without requiring the service to interpret client command syntax

### Requirement: Stable real-time run timeline
Clients SHALL present a run as an ordered timeline of user input, assistant Markdown, thinking, named tool lifecycle, approval, usage, compaction, notice, and error items. Incremental updates SHALL mutate the stable item identified by the event rather than append repeated snapshots of the same activity.

#### Scenario: Assistant text streams
- **WHEN** multiple deltas arrive for one assistant message id
- **THEN** the visible Markdown block updates in place and completion preserves that block's identity, selection, and scroll anchor

#### Scenario: Tool state changes
- **WHEN** a named tool progresses from started through updates to completed or failed
- **THEN** one timeline item retains the tool name and updates its status and summary until the terminal outcome is visible

#### Scenario: Thinking completes
- **WHEN** streamed thinking reaches its durable completed item
- **THEN** the timeline retains it in a subordinate collapsed form and permits explicit inspection without mixing it into assistant answer Markdown

### Requirement: Activity and transport are independent
Clients SHALL represent agent activity independently from connection health. The activity model SHALL distinguish at least creating, preparing, thinking, calling a named tool, awaiting approval for a named tool, responding, compacting, finalizing, cancelling, ready, and failed; transport SHALL distinguish connected, reconnecting, offline, and incompatible states.

#### Scenario: Stream reconnects during a tool call
- **WHEN** transport enters reconnecting state while the last authoritative activity is a named tool call
- **THEN** the client displays both facts and does not claim that the tool completed, failed, or was cancelled

#### Scenario: Approval is required
- **WHEN** an approval request names a tool and supplies a summary
- **THEN** every client prioritizes an awaiting-approval state with that tool name and presents the exact pending decision independently of passive connection indicators

### Requirement: Confirmed context usage
Clients SHALL display only provider-confirmed token usage against the selected model's declared context budget. They SHALL label whether usage is confirmed for the completed turn or pending for the current turn, retain the previous confirmed value while a run is active, and expose context pressure without substituting character estimates.

#### Scenario: Current turn has no usage yet
- **WHEN** a run is active and no usage event has arrived for it
- **THEN** the client keeps the previous confirmed counts, labels current usage as pending, and does not increment a speculative counter

#### Scenario: Context pressure is high
- **WHEN** confirmed total usage crosses a documented warning threshold of the active model budget
- **THEN** the client increases the prominence of the context indicator and offers the manual compaction action when that action is available

#### Scenario: Context is compacted
- **WHEN** a context-compacted event reports its reason and removed item count
- **THEN** the timeline records the outcome and the usage display waits for the next provider-confirmed usage rather than guessing the reclaimed token count

### Requirement: Scroll and focus intent survive streaming
A client SHALL follow new output only while the user remains at the timeline end. New events SHALL preserve manual scroll position, text selection, draft input, active overlay or dialog, and focused control; the client SHALL provide a direct return-to-latest affordance when unseen output exists.

#### Scenario: User inspects earlier output
- **WHEN** the user scrolls away from the end while deltas continue
- **THEN** the viewport remains anchored, an unseen-output indicator accumulates, and activating that indicator returns to the current end

#### Scenario: Approval arrives during editing
- **WHEN** the user has a non-empty draft and an approval request arrives
- **THEN** the draft remains intact, approval becomes visibly urgent, and focus changes only according to the platform's documented non-destructive attention policy

### Requirement: Shared and renderer-local preferences are separated
Service-affecting defaults such as provider, model, and reasoning level SHALL be stored as shared user preferences. Renderer-only choices such as TUI color mode, Web density, motion, and panel sizes SHALL remain client-local unless the user explicitly exports or resets them.

#### Scenario: Model default changes in Web
- **WHEN** a user saves a new shared default model in the Web configuration center
- **THEN** a later TUI draft uses that default after refreshing service configuration while retaining its own terminal theme preference

### Requirement: Client behavior is accessible by construction
All first-party clients SHALL expose the complete safe interaction path without pointer-only or color-only meaning. Status changes SHALL have textual labels, destructive operations SHALL require an explicit confirmation or equivalent deliberate gesture, and focus order SHALL remain deterministic after dialogs, reconnects, and responsive layout changes.

#### Scenario: Color is unavailable
- **WHEN** a terminal has no reliable color support or a browser user enables forced colors
- **THEN** activity, errors, approvals, and completion remain distinguishable through text and symbols rather than color alone

#### Scenario: Reduced motion is requested
- **WHEN** the platform reports reduced-motion preference
- **THEN** loaders and attention transitions avoid nonessential animation while preserving live status text
