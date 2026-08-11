## 1. Session and Presentation State

- [x] 1.1 Add canonical launch-workspace normalization plus pure current-project filtering, all-project grouping, basename disambiguation, and deterministic session sorting with focused unit tests.
- [x] 1.2 Introduce the draft/creating/attached session coordinator while keeping `SessionController` service-backed, and cover exit-before-submit, first-submit serialization, creation failure, post-creation turn failure, `/new`, and explicit resume transitions.
- [x] 1.3 Add pure agent-activity derivation with connection as an independent axis, including approval, named tool, responding, thinking, preparing, cancelling, ready, reconnecting, and failure precedence tests.
- [x] 1.4 Extend transport-neutral SDK view metadata only where stable tool/activity timestamps or identities cannot remain in the CLI, and update reducer tests for replay, completion, failure, and duplicate events.

## 2. Full-Screen TUI Shell

- [x] 2.1 Expand the CLI theme for Markdown, status, activity, selection, settings, approval, success, warning, and error presentations without adding a new runtime dependency.
- [x] 2.2 Build the `TuiAltScreen` application shell with responsive header, primary transcript `ScrollView`, activity bar, multiline editor, and status footer.
- [x] 2.3 Add one modal/focus coordinator for help, model, configuration, session, status, approval, and key overlays, including focus restoration and embedded-input IME propagation.
- [x] 2.4 Implement narrow/short terminal presentation priorities so the composer and approval controls remain usable while lower-priority status details truncate or disappear.
- [x] 2.5 Replace persistent notice concatenation with structured errors, actionable overlay content, and transient alternate-screen flash feedback.

## 3. Stable Streaming Transcript

- [x] 3.1 Replace full transcript reconstruction with an ordered keyed reconciler for persisted items, assistant/thinking buffers, tool calls, approvals, notices, and errors.
- [x] 3.2 Implement stable assistant Markdown blocks that update in place across deltas and completion, including incomplete fences, lists, tables, links, wrapping, and long code blocks.
- [x] 3.3 Implement active and completed/collapsible thinking blocks plus stable named-tool lifecycle blocks that retain completed, failed, and denied outcomes without duplication.
- [x] 3.4 Preserve follow-at-end behavior, manual scroll position, and a new-output affordance while streaming; coalesce repeated view notifications into one pending render request.
- [x] 3.5 Add focused rendering tests for delta reconciliation, final-message identity, tool lifecycle identity, Markdown reflow, thinking collapse, resize, and manual-scroll intent.

## 4. Commands and Interactive Workflows

- [x] 4.1 Replace the hard-coded slash switch and help string with a typed command registry containing names, aliases, descriptions, argument hints, availability predicates, completions, and handlers.
- [x] 4.2 Connect the registry to `CombinedAutocompleteProvider` and implement abortable model, provider, session, and workspace argument completion with command-routing and editor-completion tests.
- [x] 4.3 Implement registry-driven help, key guidance, status details, abort, quit/exit, and new-session commands with state-aware refusal messages.
- [x] 4.4 Replace notice-based model selection with an interactive model picker that updates draft selection locally, updates attached idle sessions through the service, and refuses active-run changes.
- [x] 4.5 Implement `/resume` for canonical launch-workspace sessions and `/resume --all` for grouped cross-project sessions, preserving the current draft or attachment when cancelled or empty.
- [x] 4.6 Ensure slash commands never become model turns and configuration input containing possible credentials is refused, omitted from history, and never rendered.

## 5. Unified Startup and Configuration

- [x] 5.1 Move service startup, health negotiation, protocol failure, provider readiness, and draft readiness into explicit TUI startup states with bounded loaders and recovery messages.
- [x] 5.2 Build one settings/secret-input provider workflow shared by mandatory first-run setup and `/config`, showing availability without stored key or server-token values.
- [x] 5.3 Preserve safe XDG credential writes and atomic service reload behavior, distinguish disk-save from activation results, and keep the configuration overlay usable after cancel, timeout, permission, validation, or reload failures.
- [x] 5.4 Remove readline provider onboarding and startup session selection, and make ordinary launch enter an unsaved draft without calling `createSession`.
- [x] 5.5 Integrate first-prompt lazy creation, SSE attachment, one turn submission, attached-session retry after turn failure, and confirmed model context-budget loading into the application shell.

## 6. Usage, Quality Gates, and Terminal Verification

- [x] 6.1 Implement responsive status formatting for canonical workspace, selected model, draft/attached state, connection, confirmed input/output/total usage, context budget, and pending current-turn usage without estimated tokens.
- [x] 6.2 Add virtual-terminal coverage for startup draft, no empty session on exit, autocomplete, overlays, streamed Markdown, activity transitions, approval, reconnect, resize, scroll-follow, clean detach, and terminal restoration.
- [x] 6.3 Update existing CLI usage documentation and built-in help/key text for default-new behavior, `/resume`, `/resume --all`, `/new`, `/status`, `/abort`, `/config`, `/model`, `/keys`, and `/quit`.
- [x] 6.4 Run affected SDK and CLI tests plus strict TypeScript checks, then resolve all failures without weakening the specified behaviors.
- [x] 6.5 Exercise the built CLI in a real supported terminal through first-run configuration, first-prompt creation, long streamed Markdown, thinking, a named tool call, manual scrolling, approval, abort, reconnect, project-scoped resume, all-project resume, resize, IME focus, and clean shutdown; record deterministic evidence for every scenario not covered automatically.

## 7. Conversation Polish and Approval Reliability

- [x] 7.1 Compact and restyle user, assistant, tool, thinking, notice, and empty transcript blocks so message ownership and hierarchy remain clear without excessive vertical whitespace or duplicated tool labels.
- [x] 7.2 Replace the shortcut-only approval presentation with an opaque focused action dialog that supports arrows, Enter, y/n, pending feedback, retry-safe failure handling, and deterministic focus restoration.
- [x] 7.3 Add focused transcript and approval interaction tests, then verify the approval round trip in a real terminal.
- [x] 7.4 Refine the full-screen hierarchy with a separated responsive header, turn-grouped conversation timeline, guided Agent Markdown, active streaming cursor, compact token footer, and an explicit finalizing state.
- [x] 7.5 Stream provider final text and reasoning through durable protocol delta events, batch assistant fragments to a bounded render cadence, preserve stable message identities through completion, and clear incomplete buffers on terminal runs.
- [x] 7.6 Cover stream persistence, replay convergence, terminal cleanup, streaming presentation, and responsive layout in focused tests; verify a real provider response visibly enters responding state before completion.
- [x] 7.7 Dock opaque command and approval overlays below the fixed header, use credential-aware defaults (`deepseek-v4-flash` or `gpt-5.6-terra`), request high reasoning only for declared-capable models, and recognize Ctrl+T under legacy and Kitty keyboard protocols; cover the wire request and real terminal behavior.
- [x] 7.8 Prefer DeepSeek when both provider credentials are configured and no user preference exists, persist every successful `/model` selection, restore the exact available provider/model on the next launch, and cover both precedence paths in focused and real-terminal tests.
- [x] 7.9 Preserve DeepSeek reasoning returned as segmented provider-native `raw_content`, reconcile it before publishing `thinking.done`, and verify `Ctrl+T` reveals the real text in a terminal.
- [x] 7.10 Make `Ctrl+T` collapse the currently expanded item, open a newest-first focused selector when multiple completed thinking items exist, scroll to the chosen item, and cover selection, focus restoration, and real multi-turn terminal behavior.
- [x] 7.11 Follow model selection with a capability-aware reasoning-intensity picker, default to high when supported, display and persist the selection, carry it through the public turn contract into provider model settings, and cover persistence, request propagation, and real-terminal selection.
- [x] 7.12 Apply the provider-specific Responses API effort tables and defaults (DeepSeek `high`, OpenAI `medium`), pass exact `none`/`xhigh`/`max` values on the wire, frame the complete `/config` workflow consistently, and suppress duplicate terminal Ctrl+T sequences after collapsing thinking.
