## ADDED Requirements

### Requirement: Native web search setting
The service SHALL load a non-secret native web search enablement setting from `config.toml` with file-first precedence over `TYPED_CODE_NATIVE_WEB_SEARCH` and a built-in default of enabled. The setting SHALL NOT be a secret and SHALL NOT be accepted as a command-line flag.

#### Scenario: Default enables native web search
- **WHEN** neither `config.toml` nor `TYPED_CODE_NATIVE_WEB_SEARCH` specifies native web search
- **THEN** the service treats native web search as enabled

#### Scenario: Configuration file disables native web search
- **WHEN** `config.toml` sets `tools.native_web_search` to false and `TYPED_CODE_NATIVE_WEB_SEARCH` is true
- **THEN** the service disables native web search

#### Scenario: Environment supplies a missing setting
- **WHEN** `tools.native_web_search` is absent from `config.toml` and `TYPED_CODE_NATIVE_WEB_SEARCH` is false
- **THEN** the service disables native web search

### Requirement: Public web search capability
Model listing and session model metadata SHALL include whether the advertised model profile offers provider-hosted web search.

#### Scenario: List models includes web search capability
- **WHEN** a client lists models
- **THEN** each DeepSeek and CLIProxy model entry includes `capabilities.web_search` set to true when native web search is part of that profile
