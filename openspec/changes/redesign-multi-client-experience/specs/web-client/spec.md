## Purpose

Defines the production local browser client, its same-origin authentication boundary, responsive session workspace, real-time agent interaction, and browser-specific safety and accessibility behavior.

## ADDED Requirements

### Requirement: Version-matched same-origin Web application
The active user-scoped service SHALL serve the production Web application and its API from one loopback origin. The application assets SHALL identify the same client/service protocol compatibility range selected by the managed installation and SHALL fail clearly rather than run against an incompatible API.

#### Scenario: Open the installed Web client
- **WHEN** the user invokes `typed-code web` with a compatible managed service active
- **THEN** the command resolves that service, opens its loopback Web origin, and the page negotiates the versioned public contract before showing session controls

#### Scenario: Web assets and service are incompatible
- **WHEN** cached or stale assets do not support the running service protocol
- **THEN** the page stops command submission, displays both versions, and offers a cache-safe reload or service upgrade diagnostic

### Requirement: One-time browser bootstrap
`typed-code web` SHALL mint a random, single-use, short-lived bootstrap credential through an authenticated non-browser command path and pass it to the opened page without exposing the long-lived service bearer token. Successful redemption SHALL establish an HttpOnly, SameSite=Strict browser session scoped to the loopback service origin; bootstrap values SHALL expire, be consumed atomically, and be redacted from logs.

#### Scenario: Redeem a valid bootstrap
- **WHEN** the opened same-origin page redeems an unused unexpired bootstrap value
- **THEN** the service consumes it once, establishes the browser session, removes the value from visible navigation state, and browser JavaScript never receives the long-lived bearer token

#### Scenario: Replay a bootstrap
- **WHEN** any client attempts to redeem a bootstrap value that was used or expired
- **THEN** the service rejects it without creating another browser session

#### Scenario: Browser request is cross-origin
- **WHEN** a state-changing browser request has a foreign Origin, invalid Host, missing anti-forgery proof, or absent browser session
- **THEN** the service rejects it before routing and does not mutate sessions, configuration, credentials, or service state

### Requirement: Browser session lifecycle
The Web client SHALL expose browser-session expiry and explicit sign-out without stopping the service or cancelling server-owned runs. Session cookies SHALL not be readable by page JavaScript or persisted in browser local storage.

#### Scenario: Sign out during a run
- **WHEN** the user signs out while a server run is active
- **THEN** the browser subscription closes and the browser session is invalidated while the run remains active for later reattachment

#### Scenario: Browser session expires
- **WHEN** an authenticated browser session reaches its idle or absolute expiry
- **THEN** further protected requests are rejected and the page directs the user to run `typed-code web` again without discarding local visual preferences

### Requirement: Responsive session workspace
The Web client SHALL provide a desktop layout with a resizable session/workspace rail, primary run timeline, persistent composer, contextual activity/usage region, and action surfaces. At narrower widths it SHALL collapse secondary navigation into an accessible drawer while preserving the timeline, composer, active approval, and current agent state.

#### Scenario: Use a wide viewport
- **WHEN** sufficient width is available
- **THEN** workspace-grouped sessions, selected timeline, composer, activity, model, connection, and context usage are simultaneously inspectable without overlaying the active answer

#### Scenario: Use a narrow viewport
- **WHEN** the viewport cannot fit the session rail and timeline side by side
- **THEN** navigation becomes an explicit drawer and the composer plus active approval remain reachable without horizontal page scrolling

### Requirement: Workspace-safe session creation
The Web client SHALL create sessions only from canonical workspace paths accepted by the local service. It MAY offer the workspace supplied by `typed-code web --workspace`, known recent session workspaces, and explicit path entry, but SHALL NOT expose an arbitrary local filesystem browser or infer workspace identity from browser paths.

#### Scenario: Launch from a project
- **WHEN** the user runs `typed-code web --workspace /work/project-a`
- **THEN** the new-session surface proposes the canonical accepted path for `/work/project-a` without creating a session until the first non-empty prompt is submitted

#### Scenario: Enter an invalid workspace
- **WHEN** the user enters a missing, unreadable, or disallowed path
- **THEN** the service rejects it with path-safe diagnostics and the page preserves the unsent draft for correction

### Requirement: Real-time browser run experience
The selected Web session SHALL use resumable event streaming and the shared client projection to update Markdown, thinking, named tools, approvals, usage, errors, and activity without full-page reloads. Browser tab suspension, network loss, and service replacement SHALL recover through replay or authoritative snapshot reset.

#### Scenario: Return to a suspended tab
- **WHEN** a tab resumes after missing retained events
- **THEN** the client requests events after its last sequence and applies each once before returning to live state

#### Scenario: Service is replaced by an upgrade
- **WHEN** the managed service restarts with a compatible release while the page is open
- **THEN** the page reports reconnecting, revalidates browser session and protocol identity, refreshes authoritative state, and resumes without claiming that active work was cancelled

### Requirement: Safe Markdown and code presentation
The Web client SHALL render assistant Markdown incrementally with stable blocks, readable code fences, syntax labels, copy controls, links that cannot gain opener access, and no execution of raw model-supplied HTML, scripts, event handlers, or unsafe URLs.

#### Scenario: Markdown is incomplete
- **WHEN** a streaming response contains an unclosed fence, delimiter, table, or list
- **THEN** the current block remains readable and later deltas update it without replacing surrounding timeline items

#### Scenario: Model output contains active HTML
- **WHEN** assistant text includes script, iframe, event-handler, or unsafe-link markup
- **THEN** the page displays or removes it according to the documented safe Markdown subset and executes none of it

### Requirement: Web action palette and contextual controls
The Web client SHALL expose the shared action catalog through a keyboard-openable searchable palette and contextual controls. Model selection, session recovery, configuration, compaction, transcript copy/download, diagnostics, cancellation, and approval SHALL be operable without typing terminal-only syntax.

#### Scenario: Open the action palette
- **WHEN** the user invokes the documented keyboard shortcut
- **THEN** the palette lists matching actions with descriptions, argument prompts, shortcuts, and current availability reasons, and restores prior focus when closed

#### Scenario: Export a transcript
- **WHEN** the user invokes transcript export for an attached session
- **THEN** the browser downloads a deterministic UTF-8 Markdown representation from the current authoritative snapshot without including credentials or hidden reasoning unless the user explicitly opts to include expanded reasoning

### Requirement: Accessible browser operation
The Web client SHALL meet WCAG 2.2 AA interaction requirements for keyboard access, focus visibility, names and roles, contrast, live-region restraint, error association, touch targets, zoom/reflow, and reduced motion on supported browsers.

#### Scenario: Agent state changes rapidly
- **WHEN** thinking, tool, and responding states change during one run
- **THEN** visible status updates immediately while assistive announcements are debounced and prioritize approvals, failures, and completion over every streamed delta

#### Scenario: Complete approval by keyboard
- **WHEN** an approval dialog is open
- **THEN** focus is trapped within the dialog, tool name and summary are announced, approve and reject are distinctly named, Escape follows the documented safe behavior, and focus returns to the invoking context after resolution
