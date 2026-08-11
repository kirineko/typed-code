## Purpose

Defines the minimum workspace-scoped coding tools and the Bash-based execution contract used by the MVP on supported macOS and Linux environments.

## ADDED Requirements

### Requirement: Workspace-scoped access
Every coding tool SHALL resolve its target against the session workspace and SHALL reject access that escapes the allowed workspace boundary.

#### Scenario: Access a workspace file
- **WHEN** a tool targets a path contained by the session workspace
- **THEN** the tool performs the requested permitted operation using a normalized workspace path

#### Scenario: Escape through a relative path
- **WHEN** a tool target resolves outside the session workspace through parent traversal
- **THEN** the tool rejects the operation before reading or mutating the target

#### Scenario: Escape through a symbolic link
- **WHEN** a tool target resolves outside the session workspace through a symbolic link
- **THEN** the tool rejects the operation before reading or mutating the external target

### Requirement: Minimum coding tool set
The MVP SHALL provide tools for reading files, writing files, applying targeted edits, and executing Bash commands.

#### Scenario: Read text
- **WHEN** the model requests an existing readable workspace file
- **THEN** the read tool returns bounded textual content and file metadata

#### Scenario: Write text
- **WHEN** an approved write targets a permitted workspace path
- **THEN** the write tool atomically creates or replaces the file and returns the resulting target metadata

#### Scenario: Apply a targeted edit
- **WHEN** an approved edit matches the expected current file content
- **THEN** the edit tool applies the change atomically and returns a normalized diff summary

#### Scenario: Edit precondition fails
- **WHEN** the expected current content no longer matches the file
- **THEN** the edit tool reports a conflict and does not partially modify the file

### Requirement: Unified Bash execution
The shell tool SHALL execute commands through a configured Bash executable with the session workspace as its working directory. Native PowerShell and Windows command semantics SHALL NOT be part of the MVP contract.

#### Scenario: Execute a Bash command
- **WHEN** an approved shell call is made in a supported environment
- **THEN** the service executes it using Bash, captures bounded stdout and stderr, and returns the exit status

#### Scenario: Bash is unavailable
- **WHEN** the configured Bash executable cannot be found or started
- **THEN** the service reports the environment as unsupported before accepting shell work

#### Scenario: PowerShell-specific command
- **WHEN** a command depends on PowerShell syntax or cmdlets
- **THEN** the service makes no compatibility guarantee and does not translate the command

### Requirement: Server-side approval policy
Mutating file operations and shell commands classified as side-effecting SHALL require a server-recorded approval unless the active server policy explicitly allows the operation.

#### Scenario: Mutation requires approval
- **WHEN** a tool call is classified as approval-gated
- **THEN** the tool produces a pending approval with a human-readable target and side-effect summary before execution

#### Scenario: Policy allows an operation
- **WHEN** the active server policy explicitly allows the exact operation
- **THEN** the service may execute it without an interactive approval while still recording the tool call and result

### Requirement: Mutation coordination
The service SHALL coordinate mutating tools per workspace so concurrent model tool calls cannot produce overlapping uncontrolled writes.

#### Scenario: Parallel reads
- **WHEN** multiple read-only tools are called concurrently
- **THEN** the service may execute them in parallel

#### Scenario: Concurrent mutations
- **WHEN** multiple mutating tools target the same workspace concurrently
- **THEN** the service serializes them in a deterministic order and evaluates each precondition against the latest workspace state

### Requirement: Bounded tool results
Tool outputs SHALL be bounded before they are persisted, sent to the model, or streamed to clients, while retaining enough metadata to identify truncation.

#### Scenario: Small tool output
- **WHEN** a tool result is below its configured output limit
- **THEN** the complete normalized result is returned

#### Scenario: Large tool output
- **WHEN** a tool result exceeds its configured output limit
- **THEN** the service returns a deterministic truncated result with the original size and truncation status

### Requirement: Tool cancellation
Long-running Bash execution SHALL respond to run cancellation and SHALL not leave an unmanaged child process owned by the cancelled run.

#### Scenario: Cancel a shell tool
- **WHEN** the active run is cancelled during Bash execution
- **THEN** the service terminates the owned process tree, records the interrupted tool result, and completes cancellation
