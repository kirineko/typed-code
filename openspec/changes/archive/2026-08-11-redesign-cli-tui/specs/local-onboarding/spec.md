## MODIFIED Requirements

### Requirement: First-run provider key onboarding
On startup the system SHALL determine whether any provider credential is present among the supported providers. If none are present, the CLI SHALL run a blocking `pi-tui` setup workflow that collects at least one provider key, writes it to `credentials.toml` with mode `0600`, reloads service configuration, and confirms provider availability before enabling a new-session draft. If any provider key is present, the system SHALL skip mandatory key onboarding while keeping the same configuration workflow available in-session.

#### Scenario: No provider keys configured
- **WHEN** the user starts the default entry and no supported provider credential is configured
- **THEN** the TUI guides the user to choose a provider, enter a secret key without echo, save it securely, and validate provider availability before enabling the composer

#### Scenario: At least one provider key exists
- **WHEN** the user starts the default entry and at least one supported provider key is already configured
- **THEN** the system skips mandatory key onboarding even if other providers remain unavailable

#### Scenario: Onboarding writes safe permissions
- **WHEN** onboarding creates or updates `credentials.toml`
- **THEN** the file is a current-user-owned regular file with mode `0600` and the configuration directory remains mode `0700`

#### Scenario: Onboarding reload fails
- **WHEN** a provider key is saved but the running service rejects or times out while reloading configuration
- **THEN** the setup workflow reports the secret-safe failure, keeps the configuration workflow available for correction or retry, and does not expose the entered key

## ADDED Requirements

### Requirement: Credential-aware model and reasoning defaults
The system SHALL select an available startup model in this precedence order: explicit CLI override, most recently successful `/model` selection, DeepSeek when `deepseek-v4-flash` is available, configured service default, then the first available model. A successful interactive model and reasoning-effort selection SHALL be persisted as a non-secret local preference and restored on the next launch when that exact provider/model remains available. DeepSeek SHALL expose `none`, `low`, `high`, and `max` with `high` as its default effort. OpenAI reasoning models SHALL expose `none`, `low`, `medium`, `high`, `xhigh`, and `max` with `medium` as their default effort. Models without declared reasoning support SHALL receive no inferred reasoning setting.

#### Scenario: Both provider credentials are configured without a remembered model
- **WHEN** DeepSeek and CLIProxy credentials are configured, both providers have available models, and no explicit or remembered model exists
- **THEN** the new-session draft selects `deepseek/deepseek-v4-flash`

#### Scenario: Restore the most recently selected model
- **WHEN** the user successfully selects an available model through `/model` and starts the CLI again without an explicit model override
- **THEN** the new-session draft restores that exact provider/model even when DeepSeek is also available

#### Scenario: Remembered model is unavailable
- **WHEN** the persisted provider/model is no longer available and no explicit model override is supplied
- **THEN** the CLI ignores the stale preference and selects the next available model according to the normal precedence

#### Scenario: Use provider-specific reasoning defaults
- **WHEN** the selected DeepSeek model has no remembered effort
- **THEN** the CLI selects `high`
- **WHEN** the selected OpenAI reasoning model has no remembered effort
- **THEN** the CLI selects `medium`

#### Scenario: Selected model lacks declared reasoning support
- **WHEN** a selected model profile does not declare configurable reasoning
- **THEN** the runtime omits the reasoning setting rather than assuming support

## MODIFIED Requirements

### Requirement: Slash command configuration surface
The interactive CLI SHALL intercept composer input that begins with `/` as a local command and SHALL NOT submit those lines as model prompts. `/config` SHALL open the same TUI-owned provider configuration workflow used for first-run onboarding, and configuration commands containing credentials SHALL NOT be retained in composer history or rendered in the transcript.

#### Scenario: Slash input is not a model turn
- **WHEN** the user submits a line that starts with `/` while the command is available
- **THEN** the CLI handles it locally and does not create a server turn for that line

#### Scenario: Configuration secrets are not entered as arguments
- **WHEN** the user attempts to include a provider key in `/config` command arguments
- **THEN** the CLI refuses the argument, opens or directs the user to secret input, and does not retain or render the supplied value

#### Scenario: Unknown slash command
- **WHEN** the user submits an unrecognized slash command
- **THEN** the CLI shows a short error and directs the user to command completion or help without contacting the model

### Requirement: Config menu for providers and keys
The `/config` command SHALL open a focused configuration interface that allows the user to view provider availability, set or replace supported provider API keys through secret input, save changes to the XDG credential and config files, and request a hot reload of the running local service. The interface SHALL share behavior with first-run setup, SHALL never display stored secret values, and SHALL remain usable after validation or reload failures.

#### Scenario: Open provider configuration
- **WHEN** the user invokes `/config`
- **THEN** the CLI displays supported providers and whether each is available or missing credentials without displaying stored API key values

#### Scenario: Replace a provider key
- **WHEN** the user sets a new provider key through the secret configuration workflow and saves
- **THEN** the key is written to `credentials.toml` and the running service reloads credentials so subsequent model listing and runs observe the new availability state

#### Scenario: Server token remains hidden in config UI
- **WHEN** the user opens `/config` or first-run setup
- **THEN** the UI does not display the raw server bearer token value

#### Scenario: Cancel configuration
- **WHEN** the user cancels configuration before saving
- **THEN** the CLI leaves persisted credentials and active service configuration unchanged and restores focus to the prior usable interface

#### Scenario: Reload validation fails
- **WHEN** saved configuration cannot be activated because reload validation fails
- **THEN** the CLI displays a secret-safe structured error, preserves the previously active service configuration, and allows the user to correct or retry the configuration workflow
