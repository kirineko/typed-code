## ADDED Requirements

### Requirement: Authenticated configuration reload
The service SHALL expose an authenticated command that reloads non-secret settings and credentials from the XDG configuration files (and environment fallbacks for absent file fields) into the running process. Reload SHALL recompute provider availability and refresh the CLIProxy model discovery cache when CLIProxy credentials are available. Reload SHALL NOT return secret values in responses.

#### Scenario: Reload after credential file update
- **WHEN** an authenticated client requests configuration reload after a valid credentials file update
- **THEN** subsequent health and model listing reflect the updated provider availability without process restart

#### Scenario: Reload response is secret-safe
- **WHEN** configuration reload succeeds or fails
- **THEN** the response and logs do not include API keys, server tokens, or full credential file contents

### Requirement: Idle session model switch
The service SHALL allow an authenticated client to change the provider and model of an existing session only while that session is idle and has no active run. The new selection MUST pass the same model validation rules used at session creation. The change MUST be persisted and visible in the authoritative snapshot and a durable event.

#### Scenario: Update model on idle session
- **WHEN** a client requests a model change for an idle session to a currently available model
- **THEN** the session snapshot’s provider and model fields update, revision advances, and a durable event records the change

#### Scenario: Reject model change while not idle
- **WHEN** a client requests a model change while the session phase is not idle
- **THEN** the service rejects the request with a structured conflict error and leaves the session model unchanged

#### Scenario: Reject unavailable model
- **WHEN** a client requests a model that is not available under current credentials or discovery
- **THEN** the service rejects the selection with a structured model-selection error

### Requirement: Public model context budget metadata
Model listing and session model metadata exposed by the service SHALL include the effective context token budget used for compaction and client display for each model entry.

#### Scenario: List models includes context budget
- **WHEN** a client lists models
- **THEN** each model entry includes a numeric context token budget consistent with the runtime profile rules for that provider and model
