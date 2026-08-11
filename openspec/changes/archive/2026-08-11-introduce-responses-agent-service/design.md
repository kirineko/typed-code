## Context

The repository is a new Python 3.13 project with Deepy and pi available only as references. Deepy currently couples terminal interfaces, OpenAI Agents SDK execution, provider compatibility, tools, approvals, MCP, compaction, and SQLite sessions in one process. Pi demonstrates a stronger snapshot/progress split and provides the TypeScript `pi-tui` renderer, but its experimental CBOR server protocol is tied to pi domain types and is not a standalone coding-agent service.

The selected providers both expose OpenAI-compatible Responses endpoints but have different capabilities. DeepSeek is stateless, currently supports only `deepseek-v4-flash` through Responses, always enables parallel tool calls, and silently ignores many unsupported parameters. The local CLIProxyAPI exposes multiple discovered model identifiers and implements `/v1/responses` even though its root metadata does not advertise that route. Provider behavior therefore cannot be inferred from a shared wire format alone.

See `proposal.md` for motivation and `specs/*/spec.md` for the observable contracts.

## Goals / Non-Goals

**Goals:**

- Establish one server-owned agent, tool, history, approval, and persistence boundary reusable by independent clients.
- Keep the MVP small enough to prove a complete prompt-to-tool-to-response workflow with both providers.
- Isolate Pydantic AI and provider SDK types behind an internal runtime adapter.
- Make reconnect, cancellation, approval, and process restart explicit state transitions rather than UI callbacks.
- Use one deterministic Bash execution contract on supported macOS and Linux hosts.
- Preserve extension points for a later AG-UI adapter and non-local execution backend without implementing them now.

**Non-Goals:**

- Native Windows, PowerShell, cmd.exe, WSL discovery, or cross-platform command translation.
- Web or desktop UI implementation, AG-UI/Vercel adapter endpoints, client-supplied conversation history, or frontend tools.
- Provider-native conversation state, background Responses jobs, images/files, native MCP tools, or Chat Completions fallback.
- Deepy session/config compatibility, skills, subagents, MCP, background shell management, or remote sandboxes.
- Automatic CLI-managed server startup, a combined Python/TypeScript installer, cloud multi-tenancy, or distributed durable execution.

## Decisions

### 1. Use a Python service with a strict internal layering

The Python application will be divided into protocol/API, domain orchestration, agent runtime, provider registry, persistence, and workspace execution boundaries:

```text
HTTP/SSE API
    │
    ▼
Session / Run domain
    ├── Pydantic AI runtime adapter ──▶ Responses providers
    ├── Workspace execution backend ─▶ local files and Bash
    └── SQLite repositories          ─▶ sessions and events
```

Only the runtime adapter may import Pydantic AI model/message/event types. Public Pydantic models define typed-code request, snapshot, event, and error contracts. This prevents a Pydantic AI upgrade from becoming a public protocol migration.

Alternative considered: reuse Deepy’s `run_prompt_once()` and expose its callbacks over HTTP. Rejected because lifecycle ownership, SDK items, approvals, and UI callbacks would remain coupled and would preserve the migration debt this change is intended to remove.

### 2. Construct explicit Responses models for both providers

Every provider factory returns an explicit Pydantic AI `OpenAIResponsesModel`:

- DeepSeek uses `DeepSeekProvider`, model `deepseek-v4-flash`, base URL `https://api.deepseek.com`, and the server-resolved DeepSeek credential whose environment fallback is `DEEPSEEK_API_KEY`.
- CLIProxyAPI uses `OpenAIProvider`, a configurable base URL defaulting to `http://127.0.0.1:8317/v1`, the server-resolved CLIProxyAPI credential whose environment fallback is `CLIPROXY_API_KEY`, and model IDs refreshed from `/v1/models`.

No string shorthand may select the model class, and no Chat Completions model or fallback is registered. Pydantic AI and OpenAI integration versions are pinned exactly in the lockfile.

CLIProxyAPI model list order is not authoritative. The service default provider/model comes from typed-code configuration. For the local development profile, the initial default is `cliproxy` / `gpt-5.6-sol`; startup remains healthy if it is absent, but creating a session without another valid selection fails with a structured model-selection error.

Alternative considered: model all endpoints as a generic OpenAI provider with only base URL and key. Rejected because DeepSeek requires a provider-specific model profile and the two endpoints have materially different capabilities.

### 3. Maintain explicit provider capabilities and conformance probes

Each provider/model profile declares supported modalities, reasoning levels, strict tool behavior, required tool choice, parallel tool calls, history strategy, and context/output limits. The runtime derives effective settings from that profile and never assumes that HTTP 200 means a parameter was honored.

Focused conformance tests exercise non-streaming output, SSE output, function calls, function outputs, thinking, usage, cancellation behavior, and unsupported settings against fake endpoints. Opt-in live smoke commands cover DeepSeek and the configured CLIProxyAPI without running in the default test suite.

Alternative considered: pass all Responses settings and rely on provider errors. Rejected because DeepSeek and compatible proxies may silently ignore unsupported fields.

### 4. Use a small typed-code domain protocol and keep AG-UI as a later adapter

The canonical API is server-authoritative and does not accept client-owned assistant history, tool calls, tool results, or approval state. This is intentionally stricter than AG-UI and Vercel protocols, whose normal run input permits client-supplied history.

The public event vocabulary follows common AG-UI concepts for run, message, content, tool, state, error, and custom events where semantics match. Coding-specific approval, workspace, context-compaction, and snapshot events remain typed-code domain events. A future adapter may translate these events to AG-UI without changing session storage or authorization.

Alternative considered: expose Pydantic AI `AGUIAdapter` directly as the sole API. Rejected because coding tool approvals and conversation integrity must be validated against server-persisted state, and the MVP also needs session listing, workspace ownership, model selection, abort, snapshots, and replay.

### 5. Use REST commands plus resumable SSE

The MVP API surface is versioned under `/v1`:

```text
GET  /v1/health
GET  /v1/models
GET  /v1/sessions
POST /v1/sessions
GET  /v1/sessions/{session_id}
POST /v1/sessions/{session_id}/turns
POST /v1/sessions/{session_id}/abort
POST /v1/sessions/{session_id}/approvals/{approval_id}
GET  /v1/sessions/{session_id}/events?after={sequence}
```

Commands return authoritative snapshots or accepted run identifiers. SSE carries ordered event envelopes containing `protocol_version`, per-session `sequence`, timestamp, session ID, optional run ID, event type, and typed data. Clients reconnect with the last processed sequence. If the requested range has expired, the service returns a reset signal and the client reloads a snapshot.

SSE disconnection does not cancel a run. Cancellation is a first-party server command so interrupted Pydantic AI history can be persisted consistently.

Alternative considered: WebSocket or pi’s length-prefixed CBOR protocol. Rejected for the MVP because commands are low-frequency, output is server-to-client, SSE works directly in browsers, and JSON/OpenAPI is easier to validate across Python and TypeScript.

### 6. Keep session snapshots authoritative and events replayable but not fully event-sourced

SQLite runs in WAL mode. The initial schema separates:

- `sessions`: workspace, provider/model, phase, active run, revision, timestamps;
- `runs`: status, start/end timestamps, terminal error;
- `model_messages`: ordered Pydantic AI message JSON and run association;
- `events`: public event sequence, type, normalized JSON, timestamp;
- `approvals`: tool call association, normalized request, status, decision;
- `history_archives`: replaced model history and compaction metadata.

A transaction persists a state transition and its public event before the event is published. Snapshots are computed from durable domain records and carry a monotonically increasing revision. Events provide ordered replay and audit assistance; they are not the only source of truth.

On startup, any non-terminal run without a live owning task becomes `interrupted`. The service does not attempt mid-tool or mid-token continuation; the user may submit a new turn using the preserved valid history.

Alternative considered: store one conversation JSON document or implement full event sourcing. The former makes atomic run/approval recovery difficult; the latter adds projection and migration complexity without MVP value.

### 7. Enforce one active run per session

A session manager owns at most one asyncio task and cancellation token per active session. A second prompt receives a conflict response. Multiple clients may subscribe, but mutating commands are accepted only after server authentication and validation against current durable state.

Prompt steering and queued user input are deferred. This avoids defining mid-turn ordering before the core prompt, approval, and abort paths are stable.

Alternative considered: shared/exclusive client leases like pi. Deferred because the MVP has one CLI controller and server-side active-run validation already prevents conflicting execution. Lease semantics can be introduced later without changing transcript events.

### 8. Persist approval state on the server

Approval-gated Pydantic AI tool calls are converted into durable typed-code approval records before execution. Client decisions contain only approval ID and outcome. The service verifies that the approval is pending for the authenticated session/run and resumes the exact stored call. Tool authorization is rechecked inside the execution boundary; approval is not treated as identity or workspace authorization.

The MVP policy defaults read-only workspace operations to allowed and requires approval for write, edit, and side-effecting Bash commands. Policy structure remains server-side so a later audit-mode feature does not change the client trust boundary.

Alternative considered: return deferred Pydantic AI tool requests to the client and accept them back. Rejected because a client could fabricate or alter a tool call.

### 9. Introduce one local workspace execution backend

Tools depend on a narrow execution backend even though the MVP implements only `LocalBashExecutionBackend`. The backend owns workspace path resolution, environment, child processes, cancellation, and mutation coordination. This prevents direct subprocess and unrestricted filesystem calls from spreading through agent code while avoiding premature container or SSH implementations.

The shell tool invokes a configured absolute Bash executable as:

```text
bash --noprofile --norc -c <command>
```

The working directory is the session workspace and the inherited environment is filtered by server configuration. Bash availability is checked before a session can use shell tools. There is no translation from PowerShell or cmd syntax and no Windows compatibility claim.

Read, write, and edit use native server filesystem operations but share the same normalized workspace boundary. Resolved paths, including symlink targets, must remain inside the workspace. Writes are atomic, edits require current-content preconditions, and one per-workspace mutation lock serializes file mutations and side-effecting Bash calls. Read-only operations may run concurrently.

Alternative considered: invoke each platform’s default shell. Rejected because it makes prompts, tests, quoting, and tool behavior platform-dependent. Container execution is deferred until the local service contract is proven.

### 10. Bound all tool and event payloads

Read and Bash outputs have configurable byte and line limits. Truncated results retain original size, captured size, and truncation direction. Public errors and diagnostics omit credentials, raw request headers, and unrestricted provider payloads. Complete provider SDK events are never persisted in the public event log.

This boundary protects model context, SQLite growth, SSE clients, and terminal rendering from unbounded output.

### 11. Use a reusable TypeScript SDK and a thin pi-tui CLI

The TypeScript workspace contains a transport-neutral client package and a CLI package. Request/response models are generated from the service OpenAPI document where practical; the discriminated SSE event union has a checked generated schema artifact and a reducer that applies snapshots and deltas idempotently.

The CLI uses `@earendil-works/pi-tui`, connects to an explicitly configured service, and implements session selection, transcript rendering, composer input, model selection, abort, approval, status, and reconnect. It does not start the Python server automatically in this change and never receives provider credentials.

Alternative considered: keep the CLI in Python with Textual. Rejected because pi-tui is the selected first client framework and a TypeScript SDK can be reused by later web and desktop clients.

### 12. Authenticate the local service and separate configuration from credentials

The service binds to loopback by default and requires a configured typed-code bearer token on all non-health API routes. Provider and server credentials remain server-side and are never returned in models, snapshots, events, errors, OpenAPI examples, or logs. Non-loopback serving is not documented or supported by the MVP.

The local configuration root is `${XDG_CONFIG_HOME:-~/.config}/typed-code`, using the same XDG convention on supported macOS and Linux hosts:

```text
typed-code/
├── config.toml       # non-sensitive settings
└── credentials.toml  # server token and provider API keys
```

`config.toml` contains listen settings, provider base URLs, default provider/model, Bash executable, and output/event limits. `credentials.toml` contains the typed-code server token, DeepSeek API key, and CLIProxyAPI API key. The configuration directory is created with mode `0700`; `credentials.toml` must be a regular file owned by the current user with mode `0600`. The service refuses to load an unsafe credential file rather than silently weakening the check.

Configuration-file values intentionally take precedence over matching environment variables:

```text
config.toml / credentials.toml
    >
environment variable fallback
    >
non-sensitive built-in default
```

The environment fallbacks include `TYPED_CODE_SERVER_TOKEN`, `DEEPSEEK_API_KEY`, and `CLIPROXY_API_KEY`. A field missing from its file may be supplied by its environment variable; an existing file value is never replaced by the environment. This makes a user’s local service configuration deterministic while still supporting ephemeral or CI environments that omit credential files. Secret values are not accepted through command-line flags because process listings and shell history can expose them.

A missing provider credential does not prevent the service from starting. The model catalog marks that provider `missing_credentials`, and session creation with it returns a structured credential error. A missing typed-code server token is different: the service refuses to start authenticated API routes because no client could safely authorize filesystem and shell side effects.

Alternative considered: environment-first precedence. Rejected for this local-first product because exported shell state should not silently replace an explicitly saved typed-code configuration. Operators who need environment-controlled values must omit the corresponding file field.

Alternative considered: rely only on loopback. Rejected because other local processes can reach loopback and approval endpoints authorize filesystem and shell side effects.

## Risks / Trade-offs

- [Pydantic AI and compatible provider behavior evolve quickly] → Pin exact dependencies, isolate the runtime adapter, and gate upgrades on provider conformance tests.
- [DeepSeek and CLIProxyAPI silently ignore request fields] → Use explicit capability profiles and verify effective behavior with focused probes rather than endpoint naming alone.
- [Parallel tool calls race on workspace state] → Serialize mutations per workspace and require edit preconditions while allowing concurrent reads.
- [SSE clients miss expired events] → Carry sequence and revision values, retain a bounded replay window, and force snapshot refresh when the window is unavailable.
- [A CLI disconnect leaves work running unexpectedly] → Make this behavior explicit, show active state after reconnect, and require an explicit abort command.
- [SQLite synchronous work can block the event loop] → Keep transactions small and route repository operations through a dedicated database execution boundary.
- [Python server plus TypeScript CLI complicates installation] → Ship and test them independently in the MVP; defer automatic server lifecycle and unified packaging.
- [Bash behavior differs across host versions] → Use a fixed invocation contract, detect the executable, avoid shell-profile loading, and test supported macOS and Linux environments.
- [Workspace confinement is not a complete sandbox] → Document that the server still runs with the user’s OS permissions; keep an execution-backend boundary for later sandboxing.
- [A saved credential shadows an environment value unexpectedly] → Expose each non-secret setting’s source in diagnostics, document file-first precedence, and require operators to remove a file field before environment control can take effect.
- [Persisted thinking may contain sensitive data] → Normalize and expose thinking only as configured, avoid raw provider event storage, and leave a future retention policy possible.

## Migration Plan

1. Add the new server, database, protocol, and client packages alongside the empty typed-code entrypoint; Deepy remains reference-only.
2. Create a fresh typed-code data directory and schema. No Deepy databases or configuration are read or modified.
3. Verify both provider profiles through focused fake-provider tests and opt-in local smoke commands.
4. Run the Python service explicitly, then connect the TypeScript CLI and complete one read-only turn, one approved mutation, one abort, and one reconnect/resume scenario.
5. Roll back by stopping the typed-code service and removing its new local data directory; no existing Deepy state is affected.

## Open Questions

- Exact event-retention count and byte limits may be tuned from real CLI sessions without changing the protocol or required reset behavior.
- Unified binary packaging and automatic local server startup remain a separate change after the two-process MVP is validated.
