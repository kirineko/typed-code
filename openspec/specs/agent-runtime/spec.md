## Purpose

Defines the observable model-execution contract for a Responses-only coding agent, including supported providers, streamed activity, approvals, cancellation, and history continuity.

## Requirements

### Requirement: Responses-only model execution
The runtime SHALL execute every model request through a Responses API endpoint and SHALL NOT call Chat Completions or silently fall back to another model API.

#### Scenario: Responses endpoint succeeds
- **WHEN** a configured model completes a Responses API request
- **THEN** the runtime returns the model output and records the response usage

#### Scenario: Responses endpoint is unavailable
- **WHEN** a provider does not implement the required Responses API behavior
- **THEN** the runtime fails the run with a provider compatibility error and does not retry through Chat Completions

### Requirement: MVP provider profiles
The runtime SHALL support `deepseek-v4-flash` at the DeepSeek Responses endpoint and model identifiers discovered from a configured CLIProxyAPI `/v1/models` endpoint.

#### Scenario: Select DeepSeek
- **WHEN** a session selects the DeepSeek provider
- **THEN** the runtime uses `deepseek-v4-flash` and the configured server-side DeepSeek credential

#### Scenario: Select a discovered CLIProxyAPI model
- **WHEN** a session selects a model returned by CLIProxyAPI model discovery
- **THEN** the runtime sends the run to that model through CLIProxyAPI `/v1/responses`

#### Scenario: Select an unknown local model
- **WHEN** a client selects a CLIProxyAPI model that was not discovered
- **THEN** the runtime rejects the selection before starting a run

### Requirement: Provider capability enforcement
The runtime SHALL maintain provider capabilities and reject requested behavior that the selected provider cannot reliably perform.

#### Scenario: Unsupported input modality
- **WHEN** a client submits an image or file input to an MVP provider profile that does not advertise that modality
- **THEN** the runtime rejects the input rather than silently replacing or discarding it

#### Scenario: Unsupported model setting
- **WHEN** a model setting is not supported by the selected provider profile
- **THEN** the runtime omits the setting or rejects it according to the declared profile and exposes the effective configuration to the session snapshot

### Requirement: Server-managed conversation history
The runtime SHALL build each model request from server-persisted conversation history and SHALL preserve the model and tool items needed for stateless Responses providers.

#### Scenario: Continue a DeepSeek session
- **WHEN** a user submits a later turn to an existing DeepSeek session
- **THEN** the request includes the server-persisted prior history required to continue the conversation without `previous_response_id` or provider-side conversation state

#### Scenario: History exceeds the configured budget
- **WHEN** persisted history would exceed the configured context budget
- **THEN** the runtime compacts complete history units before sending the next model request and retains an archive of the replaced history

### Requirement: Normalized run activity
The runtime SHALL emit normalized text, thinking, tool, usage, status, completion, cancellation, and error activity without exposing provider SDK objects to clients.

#### Scenario: Stream a model response
- **WHEN** the provider emits Responses API streaming events
- **THEN** the runtime emits ordered normalized activity for all supported response parts

#### Scenario: Provider returns an unknown event
- **WHEN** the provider emits an event that the runtime does not recognize
- **THEN** the runtime records a sanitized diagnostic and continues unless the event prevents correct run completion

### Requirement: Approval-gated tools
The runtime SHALL pause approval-gated tool calls before side effects occur and SHALL resume only from a server-recorded approval decision.

#### Scenario: Approve a tool call
- **WHEN** an authorized client approves a pending tool call
- **THEN** the runtime executes that exact server-recorded tool call once and continues the run with its result

#### Scenario: Reject a tool call
- **WHEN** an authorized client rejects a pending tool call
- **THEN** the runtime does not execute it and continues or ends the run with a structured denied result

#### Scenario: Fabricated approval
- **WHEN** a client submits an approval identifier that is not pending for the session and run
- **THEN** the runtime rejects the decision without executing a tool

### Requirement: Run cancellation
The runtime SHALL support first-party cancellation and persist enough interrupted history for a later user turn.

#### Scenario: Cancel an active run
- **WHEN** an authorized client requests cancellation of an active run
- **THEN** the runtime stops further model and tool work, marks the run cancelled, and publishes a terminal cancellation event

#### Scenario: Repeat cancellation
- **WHEN** cancellation is requested for an already terminal run
- **THEN** the runtime returns the existing terminal state without creating another transition


### Requirement: Model-scoped context token budgets
The runtime SHALL determine the context token budget from the selected provider and model according to these rules: DeepSeek models use **1_000_000** tokens; OpenAI-family models served through CLIProxy (model identifiers treated as OpenAI GPT-family ids such as `gpt-5.*`) use **272_000** tokens; all other or unknown models use **128_000** tokens unless a later change defines a more specific profile. Compaction and budget checks MUST use the budget of the **session’s current model**, not a single global constant for all providers.

#### Scenario: DeepSeek budget
- **WHEN** a session selects `deepseek` / `deepseek-v4-flash`
- **THEN** the effective context token budget used for history compaction is 1_000_000 tokens

#### Scenario: OpenAI-family CLIProxy budget
- **WHEN** a session selects a CLIProxy model whose identifier is an OpenAI GPT-family id such as `gpt-5.6-sol`
- **THEN** the effective context token budget used for history compaction is 272_000 tokens

#### Scenario: Unknown model budget
- **WHEN** a session selects a CLIProxy model that is neither classified as OpenAI GPT-family nor otherwise specialized
- **THEN** the effective context token budget is 128_000 tokens

#### Scenario: Budget follows model switch
- **WHEN** an idle session switches from a DeepSeek model to an OpenAI-family CLIProxy model
- **THEN** subsequent compaction decisions use the 272_000 budget for the new model