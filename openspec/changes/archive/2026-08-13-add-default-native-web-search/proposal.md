## Why

The coding agent can only read the workspace. Current facts, docs, and package versions stay unreachable unless the model shells out to `curl`, which is slower, approval-gated, and not what DeepSeek or OpenAI-family Responses already provide as a hosted `web_search` tool.

## What Changes

- Enable Pydantic AI's Responses-native `WebSearchTool` by default for DeepSeek and CLIProxy sessions.
- Advertise `web_search` on public model capabilities so clients can see whether the selected model has the native tool.
- Add a file-first kill switch `tools.native_web_search` (default `true`) so a CLIProxy upstream that rejects `web_search` can be disabled without code changes.
- Emit the existing public `tool.*` lifecycle events and persist `tool_call` / `tool_result` transcript items when the provider runs a native web search.
- Keep search provider-hosted and approval-free. Do not add a local search backend, extra search API key, DuckDuckGo fallback, or silent retry without the tool.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-runtime`: Default native web search on supported Responses profiles, stateless history replay of `web_search_call` items, and normalized public tool activity for native search.
- `agent-service`: File-first `tools.native_web_search` setting and `web_search` on public model capabilities.
- `cli-client`: Render native web search through the existing tool lifecycle presentation and activity bar.

## Impact

- Runtime agent construction, provider profiles, settings, public model catalog, and the fake Responses conformance server.
- Public protocol: additive `ModelCapabilities.web_search` field; existing `tool.*` events and transcript item types are reused.
- No new Python or TypeScript dependencies.
- Provider credentials stay on the server. Native search uses the already-configured DeepSeek or CLIProxy key.
- CLI TUI needs no new event types; it already renders `tool.started` / `tool.completed` and transcript `tool_call` / `tool_result`.
