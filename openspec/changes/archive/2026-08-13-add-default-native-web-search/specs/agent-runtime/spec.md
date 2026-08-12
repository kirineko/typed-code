## ADDED Requirements

### Requirement: Default native web search
The runtime SHALL offer a provider-hosted web search tool on MVP DeepSeek and CLIProxy Responses runs when native web search is enabled. The tool SHALL be available independently of workspace file tools. Native web search SHALL NOT require a client approval.

#### Scenario: DeepSeek run includes native web search
- **WHEN** a DeepSeek session starts a run and native web search is enabled
- **THEN** the Responses request includes the provider-hosted web search tool together with any enabled workspace function tools

#### Scenario: CLIProxy run includes native web search
- **WHEN** a CLIProxy session starts a run and native web search is enabled
- **THEN** the Responses request includes the provider-hosted web search tool

#### Scenario: Workspace is unavailable
- **WHEN** a run starts with native web search enabled and workspace file tools cannot be bound
- **THEN** the runtime still offers the provider-hosted web search tool

#### Scenario: Native web search is disabled
- **WHEN** native web search is disabled in service settings
- **THEN** the runtime omits the provider-hosted web search tool from the model request

#### Scenario: Native web search does not pause for approval
- **WHEN** the selected model invokes provider-hosted web search
- **THEN** the runtime does not create a pending approval and continues the run with the provider-executed search result

### Requirement: Native web search history continuity
The runtime SHALL persist provider-hosted web search call and result items in server-managed conversation history and SHALL send those items back on later stateless Responses turns.

#### Scenario: Continue after a web search turn
- **WHEN** a later user turn continues a session whose prior history includes a provider-hosted web search
- **THEN** the next Responses request includes the persisted web search call item so the provider can restore the search result without `previous_response_id`

### Requirement: Native web search public activity
The runtime SHALL emit normalized public tool lifecycle activity for provider-hosted web search without exposing provider SDK objects, raw search payloads, or unrestricted source lists to clients.

#### Scenario: Stream a native web search
- **WHEN** the provider starts and completes a hosted web search during a run
- **THEN** the runtime emits ordered `tool.started` and terminal `tool.completed` or `tool.failed` events with a stable tool identifier, the tool name `web_search`, and a sanitized query or result summary

#### Scenario: Persist search in the snapshot
- **WHEN** a native web search reaches a terminal state
- **THEN** the authoritative snapshot transcript includes matching `tool_call` and `tool_result` items that reconstruct the same sanitized presentation after replay or snapshot refresh

### Requirement: Provider-native thinking deltas
The runtime SHALL stream displayable reasoning from both standard thinking content deltas and provider-native reasoning fields. It SHALL NOT wait until a thinking part ends to emit the remaining native reasoning.

#### Scenario: Stream DeepSeek raw reasoning
- **WHEN** a provider streams reasoning through native fields such as `raw_content` rather than `content_delta`
- **THEN** the runtime emits incremental `thinking.delta` events for that reasoning while the part is in progress

#### Scenario: Short content does not hide longer native reasoning
- **WHEN** a thinking part has a short `content` value and a longer native reasoning payload
- **THEN** the public thinking text uses the longer displayable payload
