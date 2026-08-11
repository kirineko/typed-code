## Why

Deepy’s current in-process UI, OpenAI Agents SDK runner, provider compatibility code, and session lifecycle are too tightly coupled to support CLI, web, and desktop clients without duplicating agent behavior. A new server-authoritative foundation is needed now so the first CLI MVP is built on the same Responses-only service boundary that future clients can reuse.

## What Changes

- Introduce a Python agent service built on Pydantic AI and explicit `OpenAIResponsesModel` instances; Chat Completions and automatic API fallback are out of scope.
- Support `deepseek-v4-flash` through the DeepSeek Responses API and locally discovered CLIProxyAPI models through its `/v1/responses` endpoint.
- Add server-authoritative sessions, runs, model history, approvals, snapshots, and resumable ordered events persisted in SQLite.
- Expose versioned JSON command APIs and an SSE event stream suitable for independent CLI, web, and desktop clients; the MVP implements only the CLI client.
- Add a TypeScript client SDK and a `pi-tui`-based interactive CLI for creating, resuming, prompting, observing, approving, and aborting sessions.
- Provide the minimum coding tool set: workspace-scoped read, write, edit, and Bash execution, with server-side approval and mutation coordination.
- Target macOS and Linux environments that provide Bash. Native Windows and PowerShell compatibility are explicitly excluded from the MVP.
- Defer web and desktop UIs, images, provider-native MCP tools, skills, subagents, background tasks, legacy Deepy session migration, distributed execution, and unified cross-runtime packaging.

## Capabilities

### New Capabilities

- `agent-runtime`: Responses-only Pydantic AI execution, provider selection, streamed model/tool activity, approvals, cancellation, and provider capability enforcement.
- `agent-service`: Server-authoritative session lifecycle, SQLite persistence, versioned command APIs, snapshots, and resumable SSE events.
- `workspace-tools`: Workspace-scoped coding tools executed through a Bash-compatible environment with approval and safe mutation coordination.
- `cli-client`: A TypeScript client SDK and `pi-tui` interactive CLI that consume the service without embedding agent runtime behavior.

### Modified Capabilities

None.

## Impact

- Establishes new Python server modules, SQLite storage, public HTTP/SSE contracts, TypeScript client packages, and CLI packaging.
- Adds Pydantic AI with its OpenAI integration, an ASGI HTTP stack, and `@earendil-works/pi-tui`.
- Provider credentials and workspace access move behind the server boundary; clients receive normalized domain state and events rather than provider or Pydantic AI objects.
- The MVP is supported only where a Bash environment is available. Windows/PowerShell support requires a later capability change.
