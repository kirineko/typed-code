## 1. Project Foundation

- [x] 1.1 Add and exactly lock the Python runtime, Pydantic AI OpenAI integration, ASGI, SQLite, testing, linting, and type-checking dependencies required by the design.
- [x] 1.2 Create the Python package boundaries for protocol, API, domain orchestration, agent runtime, providers, persistence, approvals, compaction, and workspace execution without importing reference project modules.
- [x] 1.3 Implement typed non-sensitive settings from the XDG `config.toml` for listen address, data directory, provider base URLs, default provider/model, Bash executable, and output limits, with file values taking precedence over environment fallbacks.
- [x] 1.4 Implement XDG `credentials.toml` loading for the server token and provider keys with file-first precedence, `0700` directory and `0600` current-user file enforcement, environment fallback for absent fields, provider availability states, and secret-safe errors.
- [x] 1.5 Create the TypeScript workspace with separate transport-neutral client SDK and CLI packages, exactly lock direct dependencies, and configure type checking and focused tests.

## 2. Domain Protocol and Persistence

- [x] 2.1 Define discriminated public request, model metadata, session snapshot, transcript item, approval, event envelope, and structured error models with protocol version 1.
- [x] 2.2 Define session and run phase transitions, terminal statuses, revision rules, and per-session event sequence allocation in the domain layer.
- [x] 2.3 Implement the initial SQLite schema and migrations for sessions, runs, model messages, events, approvals, and history archives with WAL mode and foreign-key enforcement.
- [x] 2.4 Implement repositories that atomically persist domain transitions with their normalized public events before publication.
- [x] 2.5 Implement authoritative snapshot construction, event replay by sequence, replay-window reset behavior, and monotonic revision updates.
- [x] 2.6 Implement startup recovery that marks abandoned non-terminal runs interrupted while preserving resumable valid history.
- [x] 2.7 Add focused tests for schema migration, transaction rollback, revision/sequence monotonicity, snapshot reconstruction, event replay/reset, and interrupted-run recovery.

## 3. Responses Provider Runtime

- [x] 3.1 Implement DeepSeek and CLIProxyAPI capability profiles covering modalities, reasoning levels, tool-choice behavior, parallel calls, history strategy, and context/output limits.
- [x] 3.2 Implement CLIProxyAPI `/v1/models` discovery, refresh, deterministic validation, and configured default selection without relying on response order.
- [x] 3.3 Implement explicit `OpenAIResponsesModel` factories using `DeepSeekProvider` for `deepseek-v4-flash` and `OpenAIProvider` for discovered CLIProxyAPI models, with no Chat Completions model registered.
- [x] 3.4 Implement the Pydantic AI runtime adapter that loads server history, executes a run, persists complete model messages, and maps framework events into normalized domain activity.
- [x] 3.5 Implement provider setting normalization that exposes effective settings and rejects unsupported modalities or invalid model selections before a request.
- [x] 3.6 Implement context budgeting, complete-unit compaction, archive persistence, and stateless DeepSeek history replay without `previous_response_id`.
- [x] 3.7 Implement first-party cancellation and persistence of interrupted Pydantic AI history with idempotent terminal transitions.
- [x] 3.8 Add fake Responses endpoints and conformance tests for text, SSE, thinking, function calls/results, usage, unknown events, unsupported settings, API failures, and confirmation that no Chat Completions request occurs.
- [x] 3.9 Add opt-in live smoke commands for configured DeepSeek and CLIProxyAPI endpoints that do not run in the default test suite or expose credentials.

## 4. Workspace Execution and Coding Tools

- [x] 4.1 Implement the local execution backend interface, allowed workspace registration, normalized path resolution, and parent-traversal/symlink escape rejection.
- [x] 4.2 Implement bounded text reads with deterministic encoding errors, metadata, and explicit truncation information.
- [x] 4.3 Implement atomic writes and preconditioned targeted edits with normalized diff summaries and no partial modification on conflict.
- [x] 4.4 Implement configured Bash detection and `bash --noprofile --norc -c` execution with workspace cwd, filtered environment, bounded stdout/stderr, exit status, and process-tree cancellation.
- [x] 4.5 Implement per-workspace mutation coordination that permits parallel reads while serializing file mutations and side-effecting Bash calls.
- [x] 4.6 Register the read, write, edit, and Bash tools with Pydantic AI and convert approval-gated calls into durable server approval records before side effects.
- [x] 4.7 Implement approval decision validation and exact-once resume for the stored tool call, including rejection and fabricated/stale approval paths.
- [x] 4.8 Add focused tests for workspace confinement, symlink escape, atomicity, edit conflicts, output bounds, Bash invocation, mutation ordering, approval gating, duplicate decisions, and cancellation cleanup.

## 5. Session Orchestration and HTTP/SSE Service

- [x] 5.1 Implement the session manager with one active asyncio run and cancellation token per session, multiple observers, and conflict rejection for concurrent prompts.
- [x] 5.2 Implement loopback-default ASGI startup, required bearer authentication on non-health routes, refusal to start without a resolved server token, provider `missing_credentials` reporting, credential redaction, and Bash readiness reporting.
- [x] 5.3 Implement health, model listing, session listing, session creation, and session snapshot routes under `/v1` with stable structured errors.
- [x] 5.4 Implement turn submission, idempotent abort, and approval decision routes against current durable session/run state.
- [x] 5.5 Implement authenticated SSE subscription, retained event replay from `after`, live fan-out, keepalive behavior, and snapshot-reset signaling.
- [x] 5.6 Ensure an SSE disconnect releases only the subscription and never implicitly cancels the server-owned run.
- [x] 5.7 Publish and check the OpenAPI document plus the discriminated SSE event schema as versioned client contract artifacts.
- [x] 5.8 Add API integration tests for authentication, file-first configuration precedence, environment fallback, unsafe credential permissions, missing provider/server credentials, session lifecycle, run conflicts, approvals, abort, reconnect/replay, expired replay, sanitized failures, and process restart.

## 6. TypeScript Client SDK

- [x] 6.1 Generate or derive versioned TypeScript request, response, snapshot, error, and event types from the checked server contract artifacts.
- [x] 6.2 Implement bearer-authenticated HTTP commands for models, sessions, turns, abort, and approval decisions with structured server error mapping.
- [x] 6.3 Implement the SSE parser and reconnect controller with last-sequence tracking, backoff, retained-event replay, and authoritative snapshot reset.
- [x] 6.4 Implement an idempotent session reducer for snapshots, message deltas, thinking, tool lifecycle, approvals, usage, terminal states, and duplicate event suppression.
- [x] 6.5 Add focused SDK tests for protocol mismatch, command failures, fragmented SSE input, reconnect, event ordering, duplicate delivery, snapshot reset, and disposal.

## 7. pi-tui CLI MVP

- [x] 7.1 Build the `pi-tui` application shell with transcript scrolling, composer, status/footer, terminal resize handling, and compatible-service startup checks.
- [x] 7.2 Implement model selection plus persisted session listing, creation, selection, and resume from authoritative snapshots.
- [x] 7.3 Implement stable transcript components for user messages, assistant text/thinking, tool lifecycle/results, errors, and context/status updates.
- [x] 7.4 Connect composer submission to idle-session turn creation and disable conflicting submissions while a run is active.
- [x] 7.5 Implement keyboard-driven abort and server-backed approval/rejection presentation using the stored approval identifier and summary.
- [x] 7.6 Implement SSE reconnect presentation, snapshot reset, connection errors, protocol errors, and non-cancelling disconnect behavior.
- [x] 7.7 Implement clean exit that restores terminal state and disposes subscriptions without stopping the explicit Python service or cancelling active work.
- [x] 7.8 Add virtual-terminal and client-fixture tests for transcript streaming, tool updates, approvals, resize, reconnect, abort, session resume, and exit cleanup.

## 8. MVP Verification and Documentation

- [x] 8.1 Document the XDG `config.toml` and `credentials.toml` layouts, file-first precedence, required permissions, environment fallbacks, separate server and CLI setup, provider configuration, supported macOS/Linux Bash environments, explicit startup, and the Windows/PowerShell non-goal.
- [x] 8.2 Run a local end-to-end CLIProxyAPI smoke scenario covering session creation, streamed response, read tool, approved mutation, persisted resume, abort, and SSE reconnect.
- [x] 8.3 Run the DeepSeek provider against the fake conformance service and, when a live credential is available, execute the opt-in `deepseek-v4-flash` text/tool smoke command.
- [x] 8.4 Verify that public OpenAPI/events contain no Pydantic AI, OpenAI SDK, provider credential, or raw provider payload types.
- [x] 8.5 Run all focused Python and TypeScript tests, project lint/type checks, contract-generation checks, and strict OpenSpec validation for the change.
