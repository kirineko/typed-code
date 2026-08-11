## Context

See `proposal.md` for motivation and the delta specs for observable behavior. The current CLI constructs a `TuiMainScreen` around one linear `Container`; every session view update rebuilds transcript `Text` components, assistant output is never rendered by the built-in Markdown component, model/configuration choices are flattened into notices, and provider/session selection occurs through readline before the TUI starts. The SDK already normalizes assistant, thinking, tool, approval, usage, error, snapshot, and replay events, so the redesign should consume that contract rather than add provider-aware client logic.

The CLI must remain a thin client: server snapshots are authoritative after attachment, provider credentials remain in XDG credential files and service memory, disconnection does not cancel a server run, and provider usage is not available until a normalized usage event is emitted. The pinned `@earendil-works/pi-tui` version already supplies alternate-screen layouts, scroll views, Markdown, overlays, loaders, selection/settings components, and slash/file autocomplete.

## Goals / Non-Goals

**Goals:**

- Give layout, focus, scrolling, modal workflows, and transient feedback one explicit owner.
- Keep draft-only state separate from service-authoritative attached-session state.
- Reconcile streamed transcript items by stable identifiers so high-frequency deltas update existing components and preserve viewport intent.
- Derive user-facing agent activity deterministically from normalized SDK state while displaying connection health independently.
- Make command metadata the single source for routing, help, completion, argument completion, and state availability.
- Reuse one secure provider-configuration workflow for startup and `/config`.
- Preserve the existing service API and global SQLite session storage while presenting sessions by canonical workspace path.

**Non-Goals:**

- Adding a project table, Git repository identity, server-side session pagination/filtering, or a new public event type.
- Estimating live token counts, exposing provider events, or moving runtime/tool execution into TypeScript.
- Supporting concurrent active sessions, deleting sessions, editing persisted transcript history, or cancelling a run merely because the UI detaches.
- Adding a plugin system, theme persistence, or native Windows support.

## Decisions

### 1. Use one alternate-screen application shell

Construct `TuiAltScreen` once and install a `VStack` layout root containing:

```text
Header                     auto/fixed
ScrollView(Transcript)     grow=1, minSize=1, follow=end, primary=true
ActivityBar                auto
Composer(Editor)           auto, shrink=1
StatusFooter               auto
```

The transcript scroll view owns mouse, trackpad, and keyboard scrolling. When it is following the end, streamed output remains visible; once the user scrolls away, new content does not change `scrollTop`, and the activity/footer area exposes a new-output affordance that returns to the end. Narrow layouts keep the composer and active approval visible, shorten the workspace/model labels, and omit low-priority status details before truncating primary activity.

Secondary workflows use capturing overlays. A small modal coordinator owns the active overlay handle and previous focus target so closing a picker or dialog restores focus deterministically. Brief non-actionable notices use alternate-screen flash messages rather than being concatenated into the persistent status line.

Alternative considered: retain `TuiMainScreen` and terminal scrollback. Rejected because it cannot reserve independent transcript, composer, activity, and footer regions and makes scroll-follow intent application-invisible. `TuiAltScreen` restores the final document on clean stop, which limits the scrollback trade-off.

### 2. Separate draft coordination from remote session control

Introduce an application-level session coordinator with a discriminated state:

```text
booting
  -> draft { launchWorkspace, canonicalWorkspace, provider, model }
  -> creating { draft, prompt }
  -> attached { controller }
```

`SessionController` continues to own only service-backed attachment, snapshots, SSE lifecycle, turns, aborts, approvals, and attached-session model changes. It does not synthesize a fake snapshot for a draft.

On the first non-empty draft submission, the coordinator:

1. disables duplicate submission and enters `creating`;
2. calls `createSession` with the canonical workspace and selected provider/model;
3. attaches the returned session and starts SSE after its current sequence;
4. submits the prompt once through the attached controller;
5. remains attached if turn submission fails after session creation, allowing retry without another session.

If session creation itself fails, it returns to the same draft with the editor text preserved. `/new` disposes only the client subscription, never aborts the prior server run, and creates a fresh draft for the canonical launch workspace. `/resume` similarly discards only unsaved draft state before attaching the chosen snapshot.

Alternative considered: create a service session immediately at launch. Rejected because ordinary launch followed by exit would persist empty sessions and degrade `/resume` usability. Alternative considered: represent drafts as synthetic `SessionViewState`. Rejected because it would mix client defaults with server-authoritative snapshots and complicate command availability.

### 3. Treat canonical workspace path as the project key

Normalize the launch workspace once before constructing the draft, using an absolute real path consistent with service-side `Path.resolve()` behavior. Keep both a display path and canonical key. Persisted session summaries are grouped and compared by exact `workspace_path` equality.

`/resume` fetches the existing flat session list, filters to the canonical launch workspace, and sorts by `updated_at` descending with `session_id` as a deterministic tie-breaker. The explicit all-project view groups by full canonical path; labels use the basename and add parent path context when basenames collide. Resuming another project's session updates the attached header to that snapshot's workspace, while `/new` still targets the launch workspace unless an explicit workspace argument is supplied.

Alternative considered: introduce a project entity or infer Git roots/remotes. Rejected because directory workspaces are already the service contract, non-Git workspaces are supported, and Git worktrees and nested workspaces would require unresolved identity semantics. Alternative considered: add a filtered list API immediately. Rejected because the local session volume does not justify expanding the public protocol; client-side filtering uses data already present in `SessionSummary`.

### 4. Reconcile transcript components by stable item ID

Replace full `TranscriptView` reconstruction with a reconciler that owns an ordered list and keyed component map. Persisted transcript items use their protocol `id`; in-flight assistant/thinking buffers use their stream IDs; tools use `tool_call_id`. Reconciliation creates a component only for a new key, updates mutable state on an existing component, and removes transient entries only after their durable transcript replacement is present.

Use purpose-specific components:

- user message block;
- assistant block containing one `Markdown` instance updated with `setText()` during and after streaming;
- thinking block with active and completed/collapsed presentations;
- tool block with stable name, summary, lifecycle status, and terminal outcome;
- system notice and structured error blocks;
- approval presentation shared with the approval overlay.

Coalesce multiple view notifications into at most one pending TUI render request. This preserves Markdown render caches and avoids reconstructing completed history for each delta. The final assistant event updates the same logical block rather than replacing a raw streaming line with a differently styled final line. Incomplete Markdown remains in the same renderer; final syntax is allowed to reflow as later deltas close structures.

Alternative considered: use plain text until completion and swap to Markdown. Rejected because it produces a large visual transition at completion and violates stable presentation. Alternative considered: parse every delta into a newly allocated component tree. Rejected because it discards component caches and scales with total transcript size per delta.

### 5. Derive activity as a pure presentation model

Create a pure derivation from `SessionViewState` and coordinator state. Connection remains a separate axis. Agent activity precedence is:

```text
creating/cancelling application operation
pending approval
active nonterminal tool
active assistant buffer
active thinking buffer
attached phase=running
attached/draft ready
terminal failure
```

The resulting presentation includes a stable kind, optional tool name/summary, and optional active content identifier. Approval outranks tool activity because it requires user action; an active tool outranks buffered response/thinking because it is the current external action. Reconnecting does not overwrite activity—it is rendered alongside the last known run state.

Thinking that is currently streaming exposes its latest normalized content in a subordinate block. Completed thinking defaults to collapsed and can be expanded without mutating session state. No provider-specific reasoning payload is decoded by the CLI.

Alternative considered: map only `view.phase` to a label. Rejected because `running` cannot distinguish preparing, thinking, tool execution, and responding. Alternative considered: place connection inside the same enum. Rejected because a server-owned run can remain active while SSE reconnects.

### 6. Use one typed command registry

Define each command once with name, aliases, description, argument hint, availability predicate, optional async argument completion, and execute handler. Registry projections provide:

- `CombinedAutocompleteProvider` slash definitions for the editor;
- help and key overlay rows;
- submitted-command lookup and alias handling;
- state-aware refusal messages;
- model, provider, workspace, and session argument completions.

The initial registry includes `/help`, `/model`, `/config`, `/new`, `/resume`, `/status`, `/abort`, `/keys`, and `/quit`, with `/exit` and `/?` as aliases where appropriate. `/resume` opens current-project results; an explicit `--all` argument selects the grouped all-project view. Model and session data are fetched only when their picker/completion is requested and completion requests honor the provider's abort signal.

Credential values are never accepted as command arguments. `/config` arguments that appear to contain a secret are refused and excluded from editor history. Command text is never appended to the authoritative transcript or submitted as a turn.

Alternative considered: extend the current switch statement and separate help string. Rejected because routing, documentation, completion, aliases, and availability would diverge as commands grow.

### 7. Unify startup and in-session configuration

Start the TUI after local credential bootstrap has ensured a server token, then represent service startup, health negotiation, provider setup, and session readiness as UI states. Provider-key onboarding and `/config` use the same focused settings workflow:

```text
provider availability list
  -> provider selection
  -> secret input
  -> safe file write
  -> bounded service reload
  -> refreshed availability/model catalog
```

Mandatory onboarding keeps the composer unavailable until at least one provider is available. Existing safe file permissions and hot-reload rollback remain authoritative. Stored keys and the server token are never rendered; secret input owns focus and is not placed in editor history. Reload errors keep the settings overlay open with a structured, secret-safe error and a retry path.

Alternative considered: preserve readline onboarding before TUI startup. Rejected because it creates a second interaction/focus model, cannot share the in-session configuration UI, and makes startup failures visually inconsistent.

### 8. Display only confirmed usage

Keep the selected model's context budget available for both draft and attached status. After `usage.updated`, display confirmed input, output, and total usage plus the budget and percentage. During the next run, retain the last confirmed value and indicate that current-turn usage is pending. If no usage exists, show an unavailable marker, not zero. Do not derive token counts from character length.

Alternative considered: estimate tokens client-side. Rejected because provider tokenization differs, no tokenizer dependency exists, and an apparently live but inaccurate number would be misleading.

### 9. Split the current application shell by responsibility

`app.ts` becomes composition and lifecycle wiring rather than owning startup, session selection, command execution, rendering, focus, and shutdown in one function. Keep modules centered on domain responsibilities: shell/layout, session coordination, commands, transcript presentation, activity/status presentation, and configuration/session/model workflows. Do not introduce a generic UI framework or catch-all helpers.

The SDK reducer remains transport-neutral and pi-tui-free. Extend its normalized view types only if presentation needs durable event timestamps or lifecycle metadata that cannot be retained safely in the CLI reconciler.

## Risks / Trade-offs

- **[Alternate-screen users expect terminal scrollback]** → Rely on pi-tui's final-document restoration on clean stop, retain transcript scrolling and selection in-app, and verify shutdown restoration in a real terminal.
- **[Markdown reparsing can become expensive during long streams]** → Preserve keyed `Markdown` instances, coalesce render requests, and measure streaming behavior with long code blocks before tuning refresh cadence.
- **[Incomplete Markdown can temporarily reflow]** → Keep one stable assistant block and accept local reflow as syntax closes; never duplicate or swap the message at completion.
- **[First submission spans session creation and turn submission]** → Serialize the operation, preserve editor text until session creation succeeds, attach before submitting the turn, and remain attached after post-creation failures.
- **[Client-side session filtering loads all summaries]** → Accept for the local initial product; add a server filter only if measured session volume makes list latency or allocation material.
- **[Canonical paths can have platform-specific spelling]** → Use one normalization boundary and exact service-returned paths after attachment; test symlinked launch workspaces on supported platforms.
- **[Overlay focus bugs can break IME or secret input]** → Give modal focus ownership one coordinator, propagate focus into embedded input components, and cover close/cancel/resize behavior with virtual-terminal and real TUI smoke scenarios.
- **[Thinking can dominate the transcript]** → Style it as subordinate activity and collapse completed blocks by default while retaining explicit expansion.
- **[Configuration reload can save a key that is not currently active]** → Report disk-save and activation results separately, keep the overlay open, and preserve the service's existing atomic reload behavior.

## Migration Plan

1. Introduce the draft/attached coordinator and typed command/activity models behind the existing service contract.
2. Replace the shell with the alternate-screen layout and modal coordinator while retaining existing controller operations.
3. Migrate transcript rendering to keyed components and Markdown, then remove the full-rebuild/plain-text path.
4. Migrate help, model, configuration, startup, and session selection into registry-driven overlays; remove readline onboarding and startup session selection.
5. Enable lazy session creation and project-scoped `/resume`, then remove eager ordinary-launch session creation.
6. Update focused SDK/CLI tests, virtual-terminal scenarios, user-visible key guidance, and any documented startup behavior.
7. Verify resize, long streaming Markdown, manual scrolling, approval, reconnect, configuration failure, first-submit failure, `/resume`, clean shutdown, and IME focus in the applicable terminal smoke scenarios.

Rollback before release is a code rollback because the service protocol and SQLite schema are unchanged. Persisted sessions created during development remain valid and are discoverable by `/resume`; no data migration or compatibility shim is required.
