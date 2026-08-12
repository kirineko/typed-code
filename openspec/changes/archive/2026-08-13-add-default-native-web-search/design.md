## Context

See `proposal.md` for motivation. The runtime already uses explicit `OpenAIResponsesModel` instances for DeepSeek and CLIProxy. Workspace tools are local Pydantic AI function tools. Native `web_search` is a provider-executed Responses tool, not a workspace function.

Pydantic AI 2.27 registers it as `capabilities=[NativeTool(WebSearchTool())]`. `OpenAIResponsesModel` sends `{ "type": "web_search" }` and maps `web_search_call` items to `NativeToolCallPart` / `NativeToolReturnPart` (`part_kind` remains `builtin-tool-call` / `builtin-tool-return`). Persisted PAI message JSON is already the history source of truth.

`adapter.py` is already over the 600-line hard split. New binding and stream mapping MUST live in new modules.

Public `tool.*` events, `ToolCallItem`, and `ToolResultItem` already exist. The CLI already renders them. Native search currently emits none of them.

## Goals / Non-Goals

**Goals:**

- Attach native `web_search` by default on both MVP Responses profiles
- Keep it independent of workspace tool binding
- Make search visible through existing public tool activity
- Persist enough sanitized transcript state for snapshot reconstruction
- Give operators a file-first kill switch

**Non-Goals:**

- Local search backends or extra search credentials
- DuckDuckGo / `NativeOrLocalTool` fallback
- `WebFetchTool`, code interpreter, file search, or MCP native tools
- Approval for web search
- Silent retry after a provider rejects `web_search`
- Streaming visibility for workspace function tools
- `openai_include_web_search_sources` (DeepSeek `include` is unsupported)

## Decisions

### 1. Use `NativeTool(WebSearchTool())`, not `WebSearch(local=...)`

Native-only matches DeepSeek and OpenAI Responses. A local fallback would add a dependency and a second search contract. If a CLIProxy upstream rejects the tool, fail the run with a sanitized provider error.

Alternative considered: always-on with no setting. Rejected because some CLIProxy models may 400 and operators need a kill switch.

### 2. Profile + setting both gate the tool

`ProviderProfile.native_web_search` is `True` for DeepSeek and CLIProxy. Effective enablement is `settings.native_web_search and profile.native_web_search`. Public `ModelCapabilities.web_search` follows the profile (capability of the model), not the operator kill switch. The request omits the tool when the setting is false.

Alternative considered: advertise `web_search` only when the setting is on. Rejected; catalog capabilities describe the model, not the local operator preference.

### 3. Default `WebSearchTool()` options only

DeepSeek ignores `search_context_size` and `user_location`. Do not send filters, domain lists, or `openai_include_web_search_sources`.

### 4. Attach even when workspace tools are off

`_build_agent` currently builds a tools-less agent when the workspace path is missing. Native search is provider-hosted and MUST still attach. Split construction: optional workspace function tools + optional native capabilities. Bind `WebSearchTool` only on `OpenAIResponsesModel` instances so TestModel overrides and other non-Responses fakes keep their existing tool-selection behavior.

### 5. New modules instead of growing `adapter.py`

- `runtime/native_tools.py`: capability list + sanitized summaries
- Domain transitions for `record_tool_started` / `finish_tool`, following `record_thinking_delta` / `finish_thinking`
- Stream loop maps `NativeToolCallPart` / `NativeToolReturnPart` only

Do not map `FunctionToolCallEvent` in this change.

### 6. Sanitized summaries

Started summary is a query preview from `args.query` or `args.queries`. Completed summary is a short status / count. Never forward raw `sources`, provider objects, or unrestricted URLs as the public summary. Existing `tool.started.summary` / `ToolCallItem.summary` fields are enough; no protocol event change.

### 7. History is PAI message JSON

Do not hand-build `web_search_call` items. `dumps_messages` / `loads_messages` already persist native parts. Compaction should count `builtin-tool-call` / `builtin-tool-return` through the existing generic estimator.

### 8. System prompt

Mention that provider web search is available for current or external facts. Do not instruct the model to prefer `bash` + `curl` for search.

## Risks / Trade-offs

- [Some CLIProxy models reject `web_search`] → operator kill switch; no auto-retry without the tool
- [Search is slow and otherwise invisible] → public `tool.*` events are required, not polish
- [`adapter.py` line-limit regression] → extract binding and activity into new files
- [Public summaries leak provider payloads] → sanitize at the runtime boundary before persistence

## Migration Plan

- Additive protocol field `capabilities.web_search` with default `false` for older decoders that ignore unknown fields; regenerate OpenAPI after the model change
- Existing sessions keep working; the next run on an enabled profile includes the tool
- Rollback: set `tools.native_web_search = false` or revert the change
