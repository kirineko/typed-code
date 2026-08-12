## 1. Prerequisite and Contract Foundation

- [ ] 1.1 Verify `add-service-install-upgrade-commands` is implemented and its managed active-version receipt can carry a Web asset digest and protocol compatibility range; stop this change if that prerequisite is not true.
- [ ] 1.2 Add `packages/client-core` and `packages/web` workspaces with browser-safe TypeScript boundaries, current supported React tooling, deterministic production builds, and no renderer dependency in SDK or client-core.
- [ ] 1.3 Define additive Python protocol models for browser bootstrap/session state, redacted configuration resources and revisions, manual compaction, service invalidations, and structured action-relevant errors.
- [ ] 1.4 Regenerate OpenAPI and event schema artifacts, update the TypeScript protocol types, and prove Python/SDK contract drift checks cover every new request, response, event, and enum.
- [ ] 1.5 Add database migrations for hashed browser sessions and their expiry/revocation metadata, including upgrade, restart, cleanup, and managed rollback compatibility tests.

## 2. SDK Transport and Shared Stores

- [ ] 2.1 Replace the SDK's mandatory token string with explicit bearer and browser-cookie/anti-forgery authentication strategies while preserving existing CLI bearer behavior.
- [ ] 2.2 Implement typed SDK methods for browser bootstrap/session lifecycle, redacted configuration read/validate/commit, manual compaction, and service invalidation streaming.
- [ ] 2.3 Refactor selected-session stream handling into an immutable subscribable store with stable snapshot identity, exact sequence reduction, replay reset, reconnect backoff, and disposal.
- [ ] 2.4 Add a service-resource store that consumes invalidations and refetches session summaries, models, redacted configuration, health, and service identity after gaps or instance changes.
- [ ] 2.5 Add SDK tests for browser credentials and anti-forgery headers, bearer isolation, abort/disposal, duplicate and missing events, restart identity, authentication expiry, and no secret-bearing diagnostics.

## 3. Renderer-Neutral Client Core

- [ ] 3.1 Move activity derivation, connection/activity separation, context-pressure selectors, and stable timeline reconciliation from CLI-specific modules into `client-core` without importing DOM, React, Node, or pi-tui.
- [ ] 3.2 Implement immutable workspace/session composition for draft, creating, attached, reconnecting, conflicting, and expired-auth states, with explicit selectors usable by `useSyncExternalStore` and pi-tui subscriptions.
- [ ] 3.3 Define the typed action catalog, platform capability injection, argument schemas/completers, availability reasons, destructive intent, and structured action results.
- [ ] 3.4 Implement actions for help, model/reasoning selection, configuration, new/resume, status, compact, transcript copy/export, theme/display, diagnostics, abort, approvals, key guidance, and quit where platform capabilities permit.
- [ ] 3.5 Implement deterministic Markdown transcript export with session metadata, ordered timeline annotations, secret redaction, optional completed-thinking inclusion, and stable UTF-8 output.
- [ ] 3.6 Add client-core tests for action parity, state predicates, conflict reconciliation, activity precedence, parallel tool ordering, confirmed-versus-pending usage, context thresholds, export redaction, and renderer notification coalescing.

## 4. Service-Owned Configuration and Compaction

- [ ] 4.1 Implement redacted configuration read models with independent credential and shared-preference revisions, supported field constraints, configured/available/validation states, and no secret-return path.
- [ ] 4.2 Implement bounded in-memory candidate provider validation that distinguishes accepted, rejected, and unreachable outcomes without mutating durable or live settings.
- [ ] 4.3 Implement owner-only temporary writes, file and directory synchronization, atomic credential replacement, live catalog swap, backup restoration, and secret-safe logging under one configuration lock.
- [ ] 4.4 Implement revision-checked atomic shared default provider/model/reasoning updates and reject unavailable or unsupported combinations without changing active sessions.
- [ ] 4.5 Add authenticated configuration routes and SDK integration tests for validation-only requests, successful commits, stale revisions, concurrent clients, ambiguous disconnect recovery, rollback boundaries, and credential redaction from logs/events/errors.
- [ ] 4.6 Add the idle-only revision-checked idempotent session compaction command, persist its history/result, and publish normalized `context.compacted` events without guessed reclaimed tokens.
- [ ] 4.7 Add service tests for compaction success, duplicate idempotency key, turn/model/approval races, unsupported runtime, restart persistence, and subsequent model-request history correctness.
- [ ] 4.8 Add the bounded service-instance invalidation stream with resource revisions, instance identity, reset behavior, authenticated activity tracking, and no transcript or secret payloads.

## 5. pi-tui Workbench Redesign

- [ ] 5.1 Cut the TUI session coordinator over to SDK/client-core stores and actions, then remove duplicate CLI activity, availability, command, and reducer semantics.
- [ ] 5.2 Rebuild the shell as an adaptive `TuiAltScreen` layout with fixed identity header, primary follow-aware `ScrollView`, execution-spine timeline, activity row, multiline `Editor`, and prioritized usage/footer regions.
- [ ] 5.3 Reconcile user, assistant Markdown, active/completed thinking, parallel named tools, approvals, compaction, errors, and terminal outcomes as stable keyed pi-tui components that survive completion and resize.
- [ ] 5.4 Implement explicit scroll-follow/new-output behavior, jump-to-latest, thinking selection/jump/collapse, selection preservation, and off-screen approval access without forcing viewport movement.
- [ ] 5.5 Generate slash autocomplete and help from the action catalog, including state availability and safe argument completion for every supported command, and prove slash text never becomes a model turn.
- [ ] 5.6 Replace direct credential/preferences file writes with the service configuration model using `SettingsList`, masked `SecretPrompt`, validation feedback, revision conflict recovery, and focus restoration.
- [ ] 5.7 Implement model/reasoning, resume, configuration, status, diagnostics, compaction, export, theme, thinking, approval, help, and keys workflows with dimension-aware opaque overlays or full-height focused panels.
- [ ] 5.8 Add semantic terminal themes with capability detection, low/no-color modes, safe control-character handling, restrained loader animation, and reversible renderer-local preferences.
- [ ] 5.9 Add wide, narrow, short, resize, no-color, long-Markdown, parallel-tool, reconnect, approval, autocomplete, and manual-scroll component/process tests using the real pi-tui terminal path.

## 6. Browser Authentication and Static Delivery

- [ ] 6.1 Add authenticated CLI bootstrap minting with cryptographic randomness, hash-only memory storage, one-use atomic redemption, bounded expiry, optional canonical workspace, and complete log/URL redaction.
- [ ] 6.2 Add hashed persisted browser sessions with idle/absolute expiry, renewal, current-session inspection, revocation, cleanup, and isolation from CLI bearer credentials.
- [ ] 6.3 Issue HttpOnly SameSite=Strict loopback cookies and implement memory-only anti-forgery token rotation plus mandatory token, exact Origin, allowed Host, and Fetch Metadata checks on browser mutations.
- [ ] 6.4 Serve a no-store application shell and immutable fingerprinted assets with exact MIME types, release/protocol metadata, restrictive CSP and security headers, SPA route fallback, and no production CORS.
- [ ] 6.5 Implement `typed-code web [--workspace PATH] [--no-open]` before TUI startup, place bootstrap material only in the URL fragment, print only the non-secret origin, and handle unavailable/incompatible/upgrade-required services.
- [ ] 6.6 Add adversarial tests for bootstrap replay/race/expiry/restart, cookie expiry, CSRF, foreign Origin, DNS rebinding Host, malformed authority, session revocation, CSP, cache headers, bootstrap history removal contract, and browser inability to retrieve the bearer token.

## 7. React Web Client

- [ ] 7.1 Build the React application shell, bootstrap redemption, browser-session recovery, SDK/client-core store providers using `useSyncExternalStore`, error boundary, and compatible-service gate.
- [ ] 7.2 Implement the responsive workspace-grouped session rail, draft creation from bootstrap/recent/explicit canonical paths, filtering, new/resume flows, and authoritative invalidation refresh.
- [ ] 7.3 Implement the semantic execution-spine timeline with stable streamed Markdown, active/collapsed thinking, parallel named tools, approval cards, compaction notices, usage, errors, and reconnect state.
- [ ] 7.4 Implement a safe CommonMark/GFM rendering pipeline with raw HTML disabled, URL sanitization, inert model content, code language/copy controls, stable anchors, incomplete streaming input, and cached completed blocks.
- [ ] 7.5 Implement the persistent multiline composer, file/paste-safe input behavior, action palette, optional slash adapter, contextual actions, keyboard shortcuts, submit/abort state, and draft preservation.
- [ ] 7.6 Implement model/reasoning selection, redacted transactional configuration center, status/diagnostics inspector, manual compaction, transcript copy/download, local display preferences, and browser sign-out.
- [ ] 7.7 Implement wide, tablet, and narrow layouts with resizable/collapsible panels, in-flow plus sticky approval access, deterministic focus restoration, visible focus, forced-color support, and reduced motion.
- [ ] 7.8 Self-host and subset Atkinson Hyperlegible Next and JetBrains Mono, implement the semantic six-color light/dark token systems, and verify the execution spine is the only nonessential animated signature.
- [ ] 7.9 Add browser tests for first setup, draft/no-persist exit, streamed response, incomplete Markdown, thinking/tool/approval, multi-tab conflict, suspension/replay reset, upgrade reconnect, export redaction, keyboard-only operation, responsive reflow, and authentication expiry.

## 8. Performance, Accessibility, and Security Gates

- [ ] 8.1 Measure TUI and Web p50/p95 delta-to-visible latency at 30 deltas/second, renderer commits per frame, scroll-anchor stability, CPU, and memory with 1,000-item and large-code-fence transcripts; fix regressions before accepting thresholds.
- [ ] 8.2 Verify completed timeline blocks do not reconstruct on completion, event/Markdown caches release on detach, and Web find/selection/anchors remain usable without inaccessible virtualization.
- [ ] 8.3 Run keyboard, focus-order, screen-reader/live-region, zoom/reflow, contrast, forced-colors, touch-target, and reduced-motion checks against WCAG 2.2 AA acceptance scenarios.
- [ ] 8.4 Run Markdown/XSS payloads, CSP inspection, cookie/storage inspection, URL/history/referrer/log scans, cross-origin requests, service replacement, and same-user local threat-boundary checks with no bearer or provider secret exposure.

## 9. Managed Packaging and End-to-End Release Proof

- [ ] 9.1 Build Web assets before companion freezing, include their digest and supported protocol range in the managed release manifest/receipt, and reject a candidate with missing, changed, or incompatible assets.
- [ ] 9.2 Extend the Darwin ARM64 PyInstaller/DMG pipeline to package fingerprinted Web assets and local fonts reproducibly, verify no runtime CDN dependency, and enforce documented JS/CSS/font/total artifact budgets.
- [ ] 9.3 Exercise a clean managed install without Python, `uv`, or a checkout: run `typed-code web`, complete provider setup, create a workspace session, stream text/thinking/tool/approval, use TUI and Web concurrently, and retain authoritative state when either exits.
- [ ] 9.4 Exercise compatible service upgrade and rollback with open TUI/Web clients, persisted browser session, active/inactive sessions, asset cache invalidation, configuration revisions, database migration, and exact release identity.
- [ ] 9.5 Exercise offline Web asset loading and diagnostics, uninstall with retained user data/browser-session revocation policy, and reinstall without leaking or resetting existing provider credentials and sessions.
- [ ] 9.6 Update user installation, TUI/Web usage, slash/action reference, configuration recovery, browser security boundary, accessibility, troubleshooting, and release notes only after the packaged scenarios pass.
- [ ] 9.7 Run focused Python, SDK, client-core, CLI, Web, contract-drift, browser, packaging, and repository quality gates; strictly validate this OpenSpec change and record platform, bundle, performance, accessibility, security, upgrade, and rollback evidence.
