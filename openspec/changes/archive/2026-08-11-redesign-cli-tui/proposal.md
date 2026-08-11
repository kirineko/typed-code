## Why

The current CLI exposes the service's streaming events through a linear main-screen transcript, plain-text assistant rendering, dense notices, and pre-TUI readline workflows, so core agent activity and recovery controls are difficult to discover and follow. A cohesive `pi-tui` redesign is needed to make streamed Markdown, agent state, commands, configuration, and project-scoped session recovery usable without changing the thin-client boundary.

## What Changes

- Replace the linear `TuiMainScreen` presentation with a responsive `TuiAltScreen` application shell containing a fixed header, independently scrollable transcript, activity area, composer, and status footer.
- Render assistant output as stable, incrementally updated Markdown blocks while preserving the user's manual scroll position and avoiding duplicate streamed content.
- Present thinking, tool lifecycle, approval, responding, connection, error, and cancellation states as distinct, continuously updated UI states.
- Show selected model, canonical workspace, connection state, and provider-confirmed context usage in a readable status presentation without inventing live token counts.
- Introduce a single slash-command registry that drives routing, help, availability, command completion, and argument completion.
- Add interactive overlays for help, model selection, configuration, session recovery, status details, approvals, and keyboard guidance using `pi-tui` components.
- Replace pre-TUI provider and session prompts with one TUI-owned startup and configuration experience.
- **BREAKING**: Ordinary CLI launch no longer prompts to resume a historical session. It opens an unsaved new-session draft for the canonical launch workspace; the session is persisted only when the first non-empty prompt is submitted.
- Add `/resume` for current-project recovery, with an all-project view grouped by canonical workspace path, and add discoverable session, abort, status, key-help, new-session, and quit commands.
- Organize session discovery by the canonical absolute `workspace_path` already exposed by the service. Do not add a separate project database entity or infer project identity from Git metadata.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `cli-client`: Redesign interactive layout, streaming presentation, activity/status visibility, slash-command completion and controls, lazy new-session creation, and canonical-workspace session recovery.
- `local-onboarding`: Move provider configuration and startup recovery into a unified `pi-tui` workflow shared with in-session configuration.

## Impact

- Primary code impact: `packages/cli`, including the application shell, transcript components, command routing, startup/session coordination, configuration workflows, rendering, themes, and TUI tests.
- Supporting client-state impact: `packages/sdk` may retain additional normalized client-side timestamps or view metadata needed for stable tool/activity presentation; the public event vocabulary remains unchanged.
- Service impact is limited to existing session and configuration APIs. The initial implementation filters and groups the existing flat session list client-side by `workspace_path`; no new project table or session-list endpoint is required.
- No provider SDK payloads, credentials, or server-owned runtime behavior move into the TypeScript client.
- No new runtime dependency is required; the design uses the pinned `@earendil-works/pi-tui` package.
