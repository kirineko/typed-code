## ADDED Requirements

### Requirement: Default entry hides service plumbing
The default interactive CLI entry SHALL NOT require `--token` or an explicit base URL for ordinary local use when XDG credentials already contain (or can generate) a server token. Advanced flags for base URL and token MAY remain available for power users but SHALL NOT be required in the default documented path.

#### Scenario: Launch without token flag
- **WHEN** the user starts the default CLI entry without `--token` and a server token exists or can be generated under XDG credentials
- **THEN** the CLI proceeds with local authentication using the stored token

#### Scenario: Advanced explicit token still works
- **WHEN** the user supplies an explicit token flag or environment override for the server token
- **THEN** the CLI uses that token for the session according to documented precedence

### Requirement: Model selection slash command
The `/model` command SHALL present available models from the service catalog, including provider, model identifier, availability, and each model’s context token budget. While the current session is idle, selecting a model SHALL switch the current session’s provider and model through the service. While a run is active, `/model` SHALL refuse to switch and SHALL explain that the session must be idle.

#### Scenario: Switch model while idle
- **WHEN** the user runs `/model`, the session phase is idle, and the user selects an available model
- **THEN** the service updates the session’s provider and model, the CLI refreshes from the authoritative snapshot, and subsequent turns use the selected model

#### Scenario: Refuse switch while running
- **WHEN** the user runs `/model` while a run is active or the session is awaiting approval
- **THEN** the CLI does not change the session model and shows that the session must be idle

#### Scenario: Show context budgets in the picker
- **WHEN** the model picker is displayed
- **THEN** each listed model includes its configured maximum context length used for budgeting

### Requirement: Status presentation of context budget
The CLI status presentation SHALL surface approximate context usage against the **currently selected model’s** context token budget when usage information is available.

#### Scenario: Status reflects selected model budget
- **WHEN** the session uses a model whose context budget is 272000 tokens and usage is known
- **THEN** the status presentation compares usage to that 272000 budget rather than a global constant shared by all models
