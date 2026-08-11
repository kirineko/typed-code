## Purpose

Defines first-run local setup, automatic server-token and process lifecycle for ordinary users, and the in-session configuration slash-command contracts that keep provider credentials easy to manage without exposing service plumbing.

## Requirements

### Requirement: Single local entry without manual server tokens
The default interactive entry SHALL start a usable local coding session without requiring the user to supply a server bearer token or service base URL. The system SHALL generate and persist a server token under the XDG credentials file when absent, and SHALL use that token for local service authentication automatically.

#### Scenario: First launch with no credentials file
- **WHEN** a user starts the default interactive entry and no XDG credentials file exists
- **THEN** the system creates the configuration directory with mode `0700`, creates `credentials.toml` with mode `0600` containing a generated server token, and does not print that token in the interactive UI

#### Scenario: Subsequent launch reuses stored server token
- **WHEN** a user starts the default interactive entry and a valid server token already exists in credentials
- **THEN** the client authenticates with that token without prompting the user for a token flag

### Requirement: Automatic local service lifecycle
The default interactive entry SHALL ensure a compatible loopback agent service is reachable before opening the main chat UI. When it starts a service process, it SHALL stop that process on clean CLI exit. When it reuses an already-running compatible service, it SHALL NOT stop that external process on CLI exit.

#### Scenario: No local service is running
- **WHEN** the default entry cannot reach a compatible service on the configured loopback address
- **THEN** it starts the local agent service, waits until health and protocol negotiation succeed, and then opens the interactive UI

#### Scenario: Compatible service already running
- **WHEN** a compatible loopback service is already reachable with the stored token
- **THEN** the entry reuses that service and does not spawn a duplicate service process

#### Scenario: Exit after spawning service
- **WHEN** the CLI started the local service for this session and the user exits cleanly
- **THEN** the CLI stops the service process it owns and restores the terminal

### Requirement: First-run provider key onboarding
On startup the system SHALL determine whether any provider credential is present among the supported providers (DeepSeek and CLIProxy). If none are present, the system SHALL run a blocking setup flow that collects at least one provider key, writes it to `credentials.toml` with mode `0600`, and only then continues into the main UI. If any provider key is present, the system SHALL skip the key onboarding flow.

#### Scenario: No provider keys configured
- **WHEN** the user starts the default entry and neither DeepSeek nor CLIProxy credentials are configured
- **THEN** the UI guides the user to configure at least one provider key, persists the value securely, and does not open the main chat UI until at least one key is stored

#### Scenario: At least one provider key exists
- **WHEN** the user starts the default entry and at least one supported provider key is already configured
- **THEN** the system skips the key onboarding flow even if other providers remain missing

#### Scenario: Onboarding writes safe permissions
- **WHEN** onboarding creates or updates `credentials.toml`
- **THEN** the file is a current-user-owned regular file with mode `0600` and the configuration directory remains mode `0700`

### Requirement: Slash command configuration surface
The interactive CLI SHALL intercept composer input that begins with `/` as local commands and SHALL NOT submit those lines as model prompts. The command set for this change SHALL include `/config` and `/model` (and MAY include `/help`).

#### Scenario: Slash input is not a model turn
- **WHEN** the user submits a line that starts with `/` while the session is idle
- **THEN** the CLI handles it as a local command and does not create a server turn for that line

#### Scenario: Unknown slash command
- **WHEN** the user submits an unrecognized slash command
- **THEN** the CLI shows a short error and a list of supported commands without contacting the model

### Requirement: Config menu for providers and keys
The `/config` command SHALL open a configuration menu that allows the user to set or replace DeepSeek and CLIProxy API keys and to view which providers are available versus missing credentials. Saving changes SHALL persist to the XDG credential and config files and SHALL request a hot reload of the running local service configuration.

#### Scenario: Replace a provider key
- **WHEN** the user sets a new CLIProxy or DeepSeek key through `/config` and saves
- **THEN** the key is written to `credentials.toml` and the running service reloads credentials so subsequent model listing and runs observe the new availability state

#### Scenario: Server token remains hidden in config UI
- **WHEN** the user opens `/config`
- **THEN** the UI does not display the raw server bearer token value

### Requirement: Hot reload safety
When a configuration reload is requested, the service SHALL validate the new credential file permissions and contents before replacing the in-memory credential set. If the new configuration is unsafe or invalid, the service SHALL reject the reload, retain the previously loaded credentials, and return a structured error suitable for display in the CLI.

#### Scenario: Unsafe credentials file on reload
- **WHEN** a reload is requested and the credentials file has unsafe permissions
- **THEN** the service keeps the previous credentials active and reports a secret-safe configuration error

#### Scenario: Successful reload
- **WHEN** a reload is requested with a valid credentials file
- **THEN** provider availability in health and model listing updates without requiring a process restart
