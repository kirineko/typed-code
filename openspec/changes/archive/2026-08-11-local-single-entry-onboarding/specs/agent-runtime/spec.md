## ADDED Requirements

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
