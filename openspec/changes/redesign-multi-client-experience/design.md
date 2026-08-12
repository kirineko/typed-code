## Context

See `proposal.md` for motivation. The current `packages/cli` already uses `TuiAltScreen`, `VStack`, `ScrollView`, `Editor`, overlays, autocomplete, Markdown, selection lists, and settings lists. It also has stable transcript blocks and a renderer-neutral SDK reducer, but UI-derived activity, command execution, configuration file writes, session coordination, and pi-tui components still live together in the CLI. Rendering is one vertical layout; provider configuration writes `credentials.toml` from Node and then asks the service to reload it.

The Python service owns authoritative sessions, SQLite, provider runtime, ordered per-session SSE, and the user-scoped lifecycle. It reserves loopback Host/Origin checks but serves no Web assets, browser authentication, configuration mutation, service-level invalidations, or manual compaction command. `packages/sdk` requires a bearer token and one selected-session stream. The managed installation/upgrade design in `add-service-install-upgrade-commands` is a prerequisite because Web assets must be selected, verified, activated, and rolled back with the exact service release that serves them.

A browser cannot safely inherit the long-lived bearer token from `credentials.toml`, and it cannot browse arbitrary local directories. A TUI and browser also have different interaction idioms: slash commands are appropriate in the composer, while a Web client needs semantic controls and a command palette. Shared behavior therefore has to sit below both renderers without flattening them into identical layouts.

## Goals / Non-Goals

**Goals:**

- Make snapshots, event replay, run activity, usage, action availability, and conflict recovery behave identically across first-party renderers.
- Use pi-tui's layout, scrolling, autocomplete, focus, overlay, loader, selection, and Markdown capabilities rather than rebuilding terminal primitives.
- Ship a browser client from the local service without exposing the long-lived bearer token or widening the loopback/same-origin boundary.
- Make streaming readable under long responses, incomplete Markdown, parallel tool activity, approvals, reconnects, and small viewports.
- Move shared provider/default configuration behind a secret-safe service transaction API.
- Establish measurable accessibility, render-latency, memory, packaging, and security gates.

**Non-Goals:**

- Remote network exposure, cloud accounts, multi-user tenancy, collaboration, or browser access to arbitrary filesystem trees.
- Electron/Tauri/native desktop or mobile applications in this change. Their future renderers may reuse `client-core`.
- Running provider SDKs, tools, Markdown-to-HTML conversion, or authoritative session logic in any client.
- Pixel-identical terminal and Web layouts, server-side rendering, or offline agent execution.
- Sending speculative token estimates or exposing provider-native payloads.

## Decisions

### 1. Split protocol transport, interaction core, and renderer adapters

The TypeScript dependency direction becomes:

```text
                   normalized HTTP/SSE contracts
                              │
                    @typed-code/sdk
             transport auth + reducers + stores
                              │
                 @typed-code/client-core
      actions + activity + timeline selectors + exports
                 │                         │
                 ▼                         ▼
       @typed-code/cli              @typed-code/web
       pi-tui adapter               React adapter
```

`packages/sdk` remains free of React, DOM, Node filesystem, and pi-tui. It gains an authentication strategy (`BearerAuth` or browser-cookie/anti-forgery auth), typed APIs, and per-session/service stream stores. Each store exposes immutable snapshots, `subscribe`, and commands; event reduction is synchronous and ordered, while renderer notifications may be coalesced. React consumes stores with `useSyncExternalStore`, following current React guidance for state that changes outside React. TUI subscriptions update keyed components and request a pi-tui render.

`packages/client-core` depends only on the SDK. It owns:

- immutable workspace/session view composition;
- stable timeline selectors and activity precedence;
- the typed action catalog and argument completion interfaces;
- Markdown/export policy and deterministic transcript serialization;
- confirmed-usage/context-pressure selectors;
- conflict/reconnect intents and user-facing error mapping.

Platform adapters inject clipboard, download/file export, open-URL, local preferences, and quit behavior. They do not redefine action availability or service commands.

Rejected alternatives:

- Putting React state in the SDK would make non-Web clients depend on one renderer.
- Reusing CLI classes in Web would leak Node and pi-tui assumptions.
- Independent command implementations would drift in availability and destructive behavior.

### 2. Use a typed action catalog, not a universal slash parser

Every action has a stable namespaced id such as `session.new`, `session.resume`, `session.abort`, `session.compact`, `session.export`, `model.select`, `configuration.open`, `display.theme`, `diagnostics.open`, `approval.approve`, and `application.quit`. Its definition contains title, concise description, aliases, argument schema/completer, state predicate, destructive level, and an executor over injected capabilities.

The CLI maps catalog entries to `/new`, `/resume`, `/abort`, `/compact`, `/export`, `/copy`, `/model`, `/config`, `/theme`, `/doctor`, `/status`, `/keys`, `/help`, and `/quit`. `CombinedAutocompleteProvider` receives the generated pi-tui `SlashCommand[]`; unsupported or secret values never enter completion. The Web client maps the same ids to command-palette rows and contextual buttons. Composer slash parsing is enabled in first-party Web for experienced users, but is an adapter feature: the service never interprets slash text.

Action results are structured (`success`, `cancelled`, `conflict`, `unavailable`, `error`) rather than flash strings. Renderers choose toast, inline, dialog, or status presentation from the result severity while preserving catalog copy.

### 3. Model a run as one execution spine

The signature interaction is a continuous **execution spine**: a quiet vertical rail connecting the prompt, thinking, tool, approval, response, usage, and terminal outcome for one run. The rail is not decoration; it encodes order and active position.

```text
TUI                                      Web

 You  Fix the failing parser             ● Prompt
  │                                       │
  ├─ Thinking · collapsed                 ◉ Thinking       4.2s
  ├─ ◉ bash · npm test                     │  bash          running
  ├─ ! Approval · edit                    !  Approval       required
  └─ Agent                                │
     The parser now…                      ● Response        streaming
                                          └ Usage           pending
```

SDK event ids remain the reconciliation keys. Completed snapshot transcript items and in-flight buffers are merged without duplicating ids. A tool retains its name from `tool.started`; updates cannot regress terminal status. Thinking is active and readable while streaming, then subordinate and collapsed. An approval is an urgent state attached to its tool, not a disconnected footer hint. Assistant content is Markdown; tool summaries and system errors are plain inert text.

Parallel tools render as sibling branches ordered by first event sequence. Activity precedence is: failure requiring action, approval, cancelling, active tool, thinking, responding, compacting/finalizing, preparing, ready. Connection status is an independent badge/label and never overwrites that activity.

### 4. Coalesce rendering without dropping protocol state

Reducers process and sequence-check every event immediately. Renderer notifications are coalesced to one animation frame in Web and one queued pi-tui render per microtask/frame window in TUI. Approval, failure, authentication expiry, and terminal run events flush immediately. No event or delta is sampled away.

Completed timeline blocks are memoized by stable id and content revision. Only active Markdown/thinking/tool blocks re-render on a delta. Web initially uses semantic document flow plus `content-visibility`/containment and block memoization instead of aggressive list virtualization, because virtualization breaks browser find, selection, anchors, and screen-reader continuity for variable-height Markdown. A measured long-session threshold may add accessible windowing later, but only with retained anchors and search behavior.

Performance gates use a controlled stream and long transcript:

- p95 visible delta latency below 100 ms at 30 deltas/second;
- no more than one renderer commit per display frame under bursty deltas;
- stable scroll anchor while 1,000 timeline items receive updates;
- bounded event and Markdown caches after session detach;
- no full transcript component reconstruction on message completion.

### 5. Redesign the TUI as an adaptive pi-tui workbench

The main root remains an explicit `VStack`, because pi-tui can allocate terminal height and give `ScrollView` the remaining region:

```text
┌ typed-code ─ project ─ session ───────── model / reasoning ┐  fixed header
│                                                            │
│  independently scrollable execution spine                  │  grow/shrink
│  stable Markdown, thinking, tools, approvals               │
│                                                            │
├ ◉ Calling bash · npm test                 ↓ 12 new lines ──┤  activity
│ > multiline editor                                         │  auto height
├ live · ctx 84k/272k 31% · confirmed · in 70k · out 14k ───┤  footer
```

- `TuiAltScreen` owns synchronized output, mouse selection, links, and terminal restoration.
- One primary `ScrollView` uses `follow: "end"`, chaining overscroll, auto scrollbar, and explicit `scrollToEnd`; unseen output is derived from follow state plus sequence advance.
- `Editor` keeps multiline input, history, paste handling, file completion, and catalog-generated slash autocomplete. Submit disablement follows action/session state, not connection color.
- `Markdown` instances remain keyed by message id and receive a coherent theme. In-flight code fences remain valid input to the renderer; completion removes the streaming cursor without replacing the component.
- `Loader` animates only the one active activity row and stops under reduced-motion/no-animation mode. Static glyph plus text always carries meaning.
- `SelectList` handles model, reasoning, session, action, thinking, and theme choices. `SettingsList` handles non-secret configuration fields. `SecretPrompt` is retained only as the masked adapter for the service configuration API.
- Opaque overlays stay below the identity header when at least 12 rows remain for content. On short terminals, the modal coordinator switches to a full-height focused panel rather than clipping a centered box. Focus restoration is explicit.
- `HStack` is used only at widths that fit both sides; below breakpoints, header/footer/status values become prioritized stacked or truncated rows.

Priority under constraint is approval/action > composer > agent state > selected model/connection > context risk > workspace/session detail > key hints. No essential state is conveyed by color alone. ANSI capability detection selects truecolor/256/16/no-color semantic tokens; raw model/tool control characters are sanitized before components receive text.

### 6. Give the Web client a distinct local-instrument identity

`packages/web` is a client-rendered React application built as static assets. It uses semantic HTML and project-owned CSS custom properties rather than a generic component kit. No SSR or Node server exists in production.

The visual direction is a **quiet execution instrument**, not a chat bubble clone:

- `Graphite` `#151820`: primary dark canvas;
- `Slate` `#242A35`: panels and inactive spine;
- `Mist` `#E7EAF0`: primary text;
- `Signal blue` `#7FA7FF`: selection, focus, responding;
- `Approval amber` `#E0AD5A`: pending decisions and context warning;
- `Verdigris` `#6FC3A5`: confirmed success/live state.

Danger uses an accessible red derived as a semantic exception, not a decorative accent. A light theme maps the same roles rather than inverting raw hex values. `Atkinson Hyperlegible Next` is self-hosted for interface/long-form text and `JetBrains Mono` for code, paths, tokens, and identifiers; assets are subsetted WOFF2 and packaged locally, so the UI makes no font CDN request. The TUI cannot choose terminal typefaces but mirrors the same restrained hierarchy through weight, dimming, spacing, and symbols.

The execution spine is the one expressive element. Only its active node may pulse, and that motion is disabled by reduced-motion preference. Panels use few borders; spacing and the spine provide structure. User prompts are labeled blocks, not right-aligned speech bubbles. Assistant Markdown uses a readable bounded measure while code and diffs may expand to available width.

Desktop structure:

```text
┌ Workspaces / sessions ┬──────────────── Timeline ────────────────┬ Context ┐
│ filter, grouped list  │ execution spine + stable Markdown       │ activity│
│ new / resume          │                                         │ usage   │
│                       │                                         │ model   │
│                       ├─────────────────────────────────────────┤ approval│
│                       │ composer + contextual actions           │ details │
└───────────────────────┴─────────────────────────────────────────┴─────────┘
```

The context inspector is optional and collapses before the session rail. Tablet/narrow layouts retain timeline and composer, move sessions to a drawer, and present approval as an in-flow urgent card plus sticky action bar. Sizes are user-adjustable and renderer-local.

### 7. Render Markdown through a safe, streaming-tolerant policy

The public content contract remains Markdown text, not HTML. `client-core` defines the supported interpretation: CommonMark plus tables, task lists, strikethrough, autolinks, and fenced-code metadata; raw HTML is never executable. Web parses to an AST with raw HTML disabled and applies a strict URL/sanitization policy. Links opened outside the app use `noopener`/`noreferrer`; data, javascript, file, and unapproved custom schemes are rejected. TUI strips control sequences and uses pi-tui `Markdown` with OSC 8 links only through the trusted terminal adapter.

Each active assistant message reparses only its own text at the coalesced render cadence. Completed blocks cache their rendered representation. Code blocks show language, preserve indentation, provide copy, and choose wrapping per renderer: prose wraps; code defaults to horizontal containment in Web and documented clip/wrap behavior in TUI. Transcript export serializes authoritative Markdown and plain timeline annotations; hidden completed thinking is excluded unless explicitly included.

### 8. Serve Web and API from the same managed service artifact

The Web build output is copied into the Python package's immutable asset directory before PyInstaller freezes the Darwin ARM64 companion. The service application shell embeds release, asset digest, and protocol compatibility metadata. Fingerprinted assets use long immutable caching; HTML, bootstrap, session, and API responses use `no-store` as appropriate.

The managed release manifest and installed receipt from the predecessor change gain the Web asset digest/compatibility identity. Candidate preflight verifies that static assets are present and that their declared protocol range accepts the candidate service. Upgrade activation starts one candidate serving both API and Web; rollback restores both. There is no independently updated CDN bundle.

`typed-code web [--workspace PATH] [--no-open]` runs before TUI initialization. It resolves the active managed service, requests a one-time bootstrap over bearer-authenticated CLI transport, prints only the reusable non-secret origin, and opens a URL whose bootstrap value is in the fragment. Fragments are not sent in the initial HTTP request or referrer. The page redeems the value, calls `history.replaceState` to remove it, then enters the application.

### 9. Use opaque browser sessions, not bearer tokens in JavaScript

Browser authentication has two credentials with different lifetimes:

```text
CLI bearer (credentials.toml)
       │ authenticated POST
       ▼
in-memory bootstrap: random, hashed, single-use, ~60 s
       │ fragment redemption at exact loopback origin
       ▼
SQLite browser session: opaque id hash, idle + absolute expiry
       │ HttpOnly; SameSite=Strict; Path=/ cookie
       └── in-memory anti-forgery token bound to session
```

Bootstrap records are memory-only and disappear on restart. Browser sessions are stored hashed in SQLite so a compatible managed-service restart need not sign every tab out; raw cookie values are never stored. On plain loopback HTTP the cookie cannot honestly claim `Secure`; `Secure` becomes mandatory if a later HTTPS origin is introduced. The current boundary therefore relies on loopback-only bind, exact allowed Host, exact same Origin, SameSite=Strict, an unguessable session, and an anti-forgery header. State-changing browser requests also validate Fetch Metadata when present. Production CORS remains disabled.

A same-origin session endpoint returns a rotated anti-forgery token after validating the HttpOnly cookie; JavaScript holds it only in memory. Every protected mutation requires it. Logout revokes only that browser session. CSP defaults to self, forbids object/frame embedding and inline script, restricts connections to self, and uses hashed/nonced boot code if unavoidable. Model Markdown never reaches an HTML sink.

Alternatives rejected:

- Putting the bearer in a query, fragment, localStorage, or page JS gives XSS and browser history a long-lived service credential.
- A cookie without Origin/anti-forgery checks permits ambient-authority attacks.
- Broad CORS or a separate dev origin in production weakens the already established browser boundary. Development uses a loopback proxy to the same apparent origin.

### 10. Make service-owned configuration resource-specific and transactional

The service exposes a redacted configuration document with independent revisions for provider credentials and shared preferences. One mutation targets exactly one resource revision; a UI "Save all" operation presents individual commit outcomes rather than pretending that two files can be atomically replaced together.

Provider credential replacement proceeds:

```text
receive secret over authenticated local request
  → parse and construct candidate provider in memory
  → bounded validation/classify accepted|rejected|unreachable
  → write owner-only temporary credentials file
  → fsync file and directory, atomic rename
  → swap live provider/catalog under configuration lock
  → emit redacted configuration + model invalidations
```

The old file and live provider stay active until the atomic boundary. If a post-rename live swap unexpectedly fails, the service atomically restores the synchronized backup before returning failure. The secret is held in the narrow request/candidate scope, never inserted into events or structured details, and is not automatically replayed after ambiguous disconnect.

Shared provider/model/reasoning defaults use the same revision/atomic-write discipline on the existing preferences file. Renderer appearance remains local: TUI preferences in the existing client preferences location and Web preferences in origin-scoped storage containing no credentials or server authority.

### 11. Add manual compaction as an authoritative session command

`POST /v1/sessions/{id}/compact` requires expected session revision plus an idempotency key. The session manager accepts it only while idle, serializes it with turn/model/approval commands, invokes the same runtime compaction primitive used by automatic context management, persists the resulting model history and public notice, advances revision, and publishes `context.compacted` with reason and removed-item count. It never reports an invented reclaimed token value; the next provider usage remains authoritative.

The action is offered when the model/runtime supports compaction and context pressure warrants it, but remains discoverable at lower pressure. Active work returns structured conflict. Repeated idempotency keys return the committed result without compacting twice.

### 12. Add lightweight service invalidations for multi-client navigation

Per-session SSE remains the only source for transcript/run deltas and durable session sequence. A second service-instance stream publishes bounded invalidations such as `sessions.changed`, `configuration.changed`, `models.changed`, `service.replaced`, and `browser_session.expiring`. These events carry resource ids/revisions, not full secrets, transcript content, or a false total order across sessions.

The in-memory stream has a service-instance id and bounded sequence window. On gap or instance change, clients refetch session summaries, redacted configuration, models, and health. This lets a Web session rail react to another client without polling while keeping authoritative data in existing resources.

### 13. Keep browser workspace choice explicit and narrow

The Web client may use the canonical `--workspace` supplied during bootstrap, canonical workspace paths already present in authorized session summaries, or explicit user-entered paths. The service applies the existing canonical/readable/workspace policy before draft/session creation. It does not expose directory listing, file search, or path autocomplete APIs for browser navigation. Tool file contents remain visible only when already represented by bounded tool summaries/results under the session contract.

### 14. Verify behavior at renderer, contract, browser, and packaged-install layers

Tests stay at the lowest layer that owns the contract:

- SDK/client-core: reducer identities, replay reset, activity precedence, action availability, usage certainty, export redaction, and stream reconnection.
- TUI: component snapshots at wide/narrow/short dimensions plus terminal-process scenarios for autocomplete, scroll anchoring, overlays, resize, approval, and cleanup.
- Service: bootstrap races/expiry, cookie/CSRF/Host/Origin rules, configuration revision/rollback/secret redaction, compaction idempotency/conflicts, and invalidation gaps.
- Web: browser-driven first setup, session creation, streaming Markdown, thinking/tool/approval states, reconnect, keyboard palette, focus return, responsive breakpoints, reduced motion, and accessibility audit.
- Packaging: clean installed `typed-code web`, no Python/checkout, exact asset digest, offline asset load, upgrade/restart tab recovery, rollback, and no external font/script/network dependency except provider calls initiated by runs.

Security checks inspect response headers, cookie flags, URL/history/log redaction, CSP, Markdown payloads, and cross-origin/DNS-rebinding attempts. Performance measurements use deterministic generated streams and transcripts rather than subjective animation review.

## Risks / Trade-offs

- **The shared core can become a lowest-common-denominator UI framework.** Keep it to state, semantics, actions, and platform capabilities; layout and interaction composition remain renderer-owned.
- **React plus Markdown/fonts increases companion size.** Use a client-only static build, no general component library, subset local fonts, inspect bundle composition, and fail release thresholds rather than silently growing the artifact.
- **Streaming Markdown can consume CPU.** Coalesce renderer notifications, re-render only the active keyed block, cache completed blocks, and measure long code fences and tables.
- **Persisted browser sessions add local authority.** Store only hashes, bound idle/absolute lifetimes, revoke explicitly, keep the bind loopback-only, and preserve exact Host/Origin/anti-forgery checks.
- **Loopback HTTP cannot use a truthful Secure cookie.** Do not claim otherwise. The selected boundary is local-only plus strong origin/session defenses; remote or non-loopback exposure requires a separate HTTPS/auth design.
- **A local hostile process is outside browser same-origin assumptions.** Random opaque session/bootstrap values and authenticated minting prevent guessing, but a fully compromised same-user host is not a defended multi-tenant boundary.
- **Credential validation may be slow or ambiguous.** Bound it, classify rejected versus unreachable, preserve the working credential, and never auto-replay a secret after disconnect.
- **Manual compaction changes future model context.** Keep it server-authoritative, idle-only, idempotent, explicit, and visibly recorded; do not advertise a guessed token saving.
- **Service invalidations introduce another stream.** Keep it non-durable and resource-oriented; reset always means refetch, never reconstruction from invalidations.
- **Terminal capabilities vary widely.** Maintain textual fallbacks, no-color mode, dimension fixtures, and process tests on supported macOS/Linux terminals.
- **Web scope can pull in remote/cloud assumptions.** Same-origin loopback, explicit local paths, no CORS, and no account model remain hard boundaries.

## Migration Plan

1. Complete and verify `add-service-install-upgrade-commands`; add Web asset identity to its manifest/receipt before any production Web claim.
2. Extend protocol models, OpenAPI/event schemas, and SDK authentication/store interfaces additively while the current TUI remains the only renderer.
3. Extract `client-core` actions/activity/timeline/usage/export semantics and cut the existing TUI over with behavior parity tests.
4. Implement service-owned redacted configuration and move the TUI off direct credentials/preferences writes; delete obsolete client mutation helpers after packed-install migration passes.
5. Add compaction and service invalidation contracts, then complete the pi-tui workbench redesign and command additions.
6. Add browser-session/bootstrap security and static asset serving behind development-only Web entry; complete adversarial HTTP and Markdown tests before exposing `typed-code web` in production help.
7. Build the React Web client against client-core, validate responsive/accessibility/performance behavior, and package its fingerprinted assets into the companion.
8. Exercise clean managed install, first setup, streaming, approval, multi-client handoff, service upgrade, browser reconnect, rollback, offline asset loading, and uninstall data-retention behavior on supported Darwin ARM64.
9. Remove temporary feature gates only after TUI and Web contract suites, browser security checks, bundle/artifact budgets, and strict OpenSpec validation pass.
