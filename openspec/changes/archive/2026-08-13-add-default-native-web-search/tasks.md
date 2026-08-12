## 1. Profile, Settings, and Public Capabilities

- [x] 1.1 Add `native_web_search` to provider profiles for DeepSeek and CLIProxy and expose `ModelCapabilities.web_search`.
- [x] 1.2 Load `tools.native_web_search` from `config.toml` with file-first precedence over `TYPED_CODE_NATIVE_WEB_SEARCH` and default `true`.
- [x] 1.3 Add unit tests for profile advertising, default enablement, file-over-env disablement, and env fallback.

## 2. Bind Native Web Search

- [x] 2.1 Add `runtime/native_tools.py` that returns `NativeTool(WebSearchTool())` when the setting and profile allow it, using default tool options only.
- [x] 2.2 Attach native web search during agent construction even when workspace tools are unbound, and mention provider web search in the default system prompt.
- [x] 2.3 Extend the fake Responses server and a conformance test so enabled runs send `{ "type": "web_search" }` with function tools, and disabled runs omit it.

## 3. Public Tool Activity

- [x] 3.1 Add domain transitions and repository methods to persist `tool.started` plus a `tool_call` item and a terminal `tool.completed`/`tool.failed` plus a `tool_result` item.
- [x] 3.2 Map native web search stream parts to those transitions with sanitized query/result summaries and no provider payloads.
- [x] 3.3 Add runtime tests that a fake `web_search_call` stream produces public tool events, snapshot transcript items, and persisted PAI `builtin-tool-call` / `builtin-tool-return` history.

## 4. Client Reconstruction and Gates

- [x] 4.1 Confirm the CLI activity bar and transcript reconstruct `web_search` from live `tool.*` events and from snapshot `tool_call` / `tool_result` items; add a focused test only if a gap exists.
- [x] 4.2 Regenerate public contracts if `ModelCapabilities` changed and run OpenSpec strict validation plus Python and TypeScript quality gates.
