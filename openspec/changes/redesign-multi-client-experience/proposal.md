## Why

The current CLI proves the service contract and basic pi-tui shell, but its presentation logic, command behavior, configuration workflow, and streaming state are still tightly coupled to one terminal entry while the reserved Web boundary has no usable client. Once managed service installation is available, typed-code needs one coherent, observable client experience that makes real-time agent work understandable in both terminal and browser without duplicating authority or exposing long-lived credentials.

## What Changes

- Rework the TUI around pi-tui's alternate-screen layout, stable keyed components, scroll-follow semantics, overlays, autocomplete, loaders, and focus management: a fixed identity header, independently scrollable run timeline, explicit live activity rail, multiline composer, and adaptive status footer.
- Replace ad hoc slash routing with a shared typed action catalog. The TUI derives slash completion/help from it; the Web client derives a command palette and contextual actions from the same ids, argument schemas, availability rules, and user-facing copy.
- Add high-value actions for session creation/recovery, model and reasoning selection, configuration, manual context compaction, transcript export/copy, display preferences, diagnostics, cancellation, approval, and clean exit where the platform supports them.
- Preserve streamed assistant Markdown, thinking, and named tool calls as stable timeline items; improve incomplete-Markdown handling, code-block readability, collapsed completed reasoning, tool lifecycle detail, scroll anchoring, and new-output affordances.
- Make agent state and connection state independently visible, including preparing, thinking, calling a named tool, awaiting approval, responding, compacting, cancelling, reconnecting, failed, and ready states.
- Show only provider-confirmed token usage, distinguish last-confirmed usage from an in-progress turn, visualize context pressure against the selected model budget, and surface compaction outcomes without inventing live counts.
- Replace direct client-side credential-file mutation with a service-owned, redacted configuration contract that can validate and atomically persist provider credentials and shared model preferences for both terminal and browser clients.
- Add a production local Web client served by the user-scoped service, with a responsive session rail, run timeline, composer, action palette, configuration center, approval surfaces, and reconnect/replay behavior built on the shared SDK state model.
- Add a short-lived one-time browser bootstrap flow that establishes an HttpOnly same-origin session; browser JavaScript never receives the long-lived CLI/service bearer token.
- Package version-matched static Web assets with the managed service and add `typed-code web` to resolve the active service, mint a one-time bootstrap, open the browser, and report a reusable loopback URL.
- Add client accessibility and usability gates: keyboard-complete operation, visible focus, screen-reader semantics in Web, reduced-motion support, terminal resize/low-color behavior, responsive narrow layouts, and deterministic reconnect/conflict recovery.

## Capabilities

### New Capabilities

- `client-experience`: Shared action, streaming timeline, activity, usage, configuration, accessibility, and multi-client reconciliation behavior independent of a particular renderer.
- `web-client`: Same-origin local Web application, browser bootstrap authentication, responsive workspace/session navigation, and browser-specific interaction behavior.

### Modified Capabilities

- `cli-client`: Replace the MVP terminal shell with the complete pi-tui interaction model, expanded action/command surface, improved Markdown/activity/usage presentation, and adaptive layouts.
- `local-onboarding`: Move provider setup and shared preferences behind a redacted transactional service configuration flow reusable by TUI and Web.
- `agent-service`: Add browser-session authentication, static asset delivery, redacted configuration mutation, manual context compaction, and service-level invalidation needed by independent clients.

## Impact

- Depends on completion of `add-service-install-upgrade-commands`; Web assets and `typed-code web` bind to the managed active service/version receipt rather than package-local runtime discovery.
- New workspaces: `packages/client-core` for renderer-neutral state/actions and `packages/web` for the React browser client; `packages/sdk` gains transport-auth, configuration, compaction, browser-bootstrap, and service-event contracts.
- Major changes: `packages/cli` shell/components/commands, Python HTTP/auth/config/session routes and protocol models, OpenAPI/event schemas, release packaging, managed-service manifests, and macOS distribution verification.
- Persistent server data gains browser-session and one-time-bootstrap records with bounded expiry plus shared non-secret preferences; provider credentials remain in the owner-only credentials store and are never returned by public APIs.
- No remote access, cloud tenancy, collaboration lease, native desktop shell, mobile app, arbitrary browser filesystem explorer, or change to server-authoritative agent execution is introduced. Future desktop/mobile renderers may reuse `client-core`, but are not claimed by this change.
