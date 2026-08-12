## MODIFIED Requirements

### Requirement: First-run provider onboarding
After the compatible user-scoped service is active, the first interactive client SHALL query redacted provider configuration state. If no provider is usable, TUI and Web clients SHALL enter their platform-native blocking setup workflow, collect one provider credential without echoing or retaining it in ordinary input history, validate the candidate through the service, persist it atomically only under the owner-scoped credential boundary, and confirm model availability before enabling a new-session draft.

#### Scenario: First TUI launch has no provider
- **WHEN** the terminal client starts and redacted configuration reports no usable provider
- **THEN** a focused pi-tui setup surface collects and validates one credential before enabling the composer, without displaying the service bearer token

#### Scenario: First Web launch has no provider
- **WHEN** an authenticated same-origin Web client opens and no provider is usable
- **THEN** the configuration center blocks run submission, accepts a credential through a secret field, and uses the same service validation and atomic persistence contract as the TUI

#### Scenario: Candidate credential is invalid
- **WHEN** provider validation rejects a newly entered credential
- **THEN** the prior stored credential and active provider state remain unchanged, the candidate is discarded, and the client presents a secret-safe corrective error

#### Scenario: Provider validation is temporarily unreachable
- **WHEN** the provider cannot be reached well enough to validate a candidate
- **THEN** the service distinguishes unreachable from rejected, does not silently replace a working credential, and lets the user retry or explicitly save an unverified candidate only when the provider contract supports deferred validation

### Requirement: Shared configuration center
The system SHALL expose one redacted configuration model and mutation contract for supported provider credentials, provider availability, shared default provider/model/reasoning level, and relevant service-owned settings. TUI `/config` and the Web configuration center SHALL render that model using native controls and SHALL never read or write credentials files directly.

#### Scenario: Open configuration
- **WHEN** a user opens configuration in either first-party client
- **THEN** it displays supported providers, availability, whether a credential is configured, shared defaults, validation state, and safe recovery actions without returning stored secret values

#### Scenario: Replace a provider key
- **WHEN** a user submits a replacement credential that validates successfully
- **THEN** the service writes it atomically with owner-only permissions, swaps the live provider catalog, emits configuration invalidation, and subsequent clients observe the new availability

#### Scenario: Change shared defaults
- **WHEN** a user chooses an available provider, model, and supported reasoning level as defaults
- **THEN** the service validates the combination, persists it atomically, and new drafts in all clients use it without changing existing active sessions

#### Scenario: Cancel configuration
- **WHEN** the user exits before confirming changes
- **THEN** no provider credential or shared default changes and the invoking client restores its previous focus and unsent draft

### Requirement: Secret-safe configuration transport
Credential mutation SHALL be accepted only over authenticated local transports, SHALL be excluded from URLs, logs, event payloads, snapshots, analytics, autocomplete, command history, and error details, and SHALL never be returned after submission. Client renderers SHALL clear secret field memory when the workflow closes or loses authorization.

#### Scenario: Credential update succeeds
- **WHEN** the service accepts a provider credential
- **THEN** the response contains only redacted provider state and validation outcome, not the submitted or prior secret

#### Scenario: Configuration error is logged
- **WHEN** parsing, validation, persistence, or reload fails
- **THEN** diagnostics identify the provider and failure class without including credential bytes or the long-lived service token

### Requirement: Configuration transactions preserve a working service
A configuration update SHALL stage parsing and semantic validation before replacing durable files, use atomic owner-only writes, and swap live runtime settings only after the candidate is usable. Failure at any boundary SHALL preserve or restore the previous durable and live configuration.

#### Scenario: Persistence fails after validation
- **WHEN** a valid candidate cannot be atomically written or synchronized
- **THEN** the service continues using the previous live configuration and reports that no change was committed

#### Scenario: Live swap fails after durable staging
- **WHEN** runtime provider construction fails before activation
- **THEN** the service restores the previous durable configuration and catalog and reports the rollback outcome

## ADDED Requirements

### Requirement: Shared and client-local settings are explicit
Configuration UI SHALL label which values affect all local clients and which affect only the current renderer. Resetting renderer preferences SHALL not alter credentials, shared defaults, sessions, or service lifecycle settings.

#### Scenario: Reset Web appearance
- **WHEN** the user resets Web density, panel sizes, and motion preferences
- **THEN** shared provider/model defaults and TUI display preferences remain unchanged

### Requirement: Setup survives service replacement
A client SHALL recover an interrupted setup workflow after a compatible managed-service restart without retaining a secret value. It SHALL refetch redacted configuration and require credential re-entry only if the prior request did not commit.

#### Scenario: Upgrade restarts service during setup
- **WHEN** the service disconnects after credential submission but before the client receives the response
- **THEN** the reconnecting client refetches redacted provider state to determine whether the transaction committed and never retries the secret mutation automatically
