## ADDED Requirements

### Requirement: Native web search presentation
The CLI SHALL present provider-hosted web search through the existing normalized tool lifecycle and activity presentation. It SHALL NOT render provider SDK objects, raw search payloads, or unrestricted source lists.

#### Scenario: Web search is active
- **WHEN** the event stream reports a `web_search` tool in a started or running state
- **THEN** the CLI identifies the agent as calling `web_search` and updates one stable tool presentation

#### Scenario: Web search completes
- **WHEN** a native web search completes or fails
- **THEN** the CLI retains the terminal tool outcome in the transcript using the server-provided sanitized summary

#### Scenario: Snapshot reconstructs a completed search
- **WHEN** the CLI refreshes from an authoritative snapshot that contains native web search transcript items
- **THEN** the CLI reconstructs the completed search presentation without requiring the original live stream

#### Scenario: Chronological thinking, search, and answer
- **WHEN** a run emits thinking, native web search, and then assistant text
- **THEN** the CLI presents those items in that order and does not move completed searches below the finished answer

#### Scenario: Web search keeps its query summary
- **WHEN** a native web search completes with a result summary
- **THEN** the stable tool presentation retains the sanitized query from the start event rather than replacing it with only "search completed"
