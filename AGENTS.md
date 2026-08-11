# typed-code Engineering Guide

This file defines repository-wide rules for humans and coding agents. Read it before changing application code, tests, configuration, public protocols, dependencies, documentation, or OpenSpec artifacts.

RFC 2119 terms such as MUST, SHALL, SHOULD, and MAY are normative. More specific `AGENTS.md` files may add constraints for their subtree but MUST NOT weaken this file without an explicit project decision.

## 1. Sources of Truth

Use this precedence when requirements conflict:

1. Explicit user direction for the current change.
2. The active OpenSpec change, including delta specs and approved design decisions.
3. Canonical specifications under `openspec/specs/`.
4. This engineering guide.
5. Tests, implementation, and user documentation.

Do not preserve a contradiction. Update the higher-level artifact first, then bring lower-level artifacts into agreement.

## 2. Product and Architecture Boundaries

The initial product is a client-server coding agent:

- Python 3.13+ owns the agent service, domain state, provider credentials, sessions, approvals, tools, and persistence.
- Pydantic AI is isolated behind an internal agent-runtime adapter.
- Model execution uses the Responses API only. Chat Completions and silent API fallback are prohibited.
- The TypeScript SDK and `pi-tui` CLI are thin clients of the versioned server API.
- SQLite snapshots are authoritative. Ordered events support streaming, replay, and audit but are not the only source of truth.
- The MVP supports macOS and Linux hosts with Bash. Native Windows, PowerShell, cmd.exe, and automatic WSL adaptation are out of scope until specified by a later OpenSpec change.

Maintain these dependency directions:

```text
HTTP/SSE API
    │
    ▼
Session and Run Domain
    ├── Agent Runtime Adapter ──▶ Pydantic AI ──▶ Responses providers
    ├── Execution Backend     ──▶ Workspace files and Bash
    └── Repositories          ──▶ SQLite

TypeScript CLI ──▶ TypeScript SDK ──▶ Public HTTP/SSE protocol
```

The following types MUST NOT cross the public protocol boundary:

- Pydantic AI model, message, tool, deferred-call, or stream-event types.
- OpenAI or provider SDK request/response objects.
- SQLite row shapes.
- Raw provider events, headers, credentials, or unrestricted diagnostics.

## 3. Core Engineering Principles

- Correctness and observable behavior come before convenience.
- Fix problems at their source. Do not suppress errors or special-case symptoms.
- Prefer simple, explicit modules over generic frameworks or speculative abstractions.
- Reuse an existing repository pattern. Do not introduce a second convention for the same concern.
- Keep side effects at clear boundaries. Domain logic should be deterministic and testable.
- Avoid needless allocation, copying, serialization, and repeated computation on streaming paths.
- Do not retain compatibility shims unless an active specification requires them.
- Do not add retries, telemetry, caching, provider capabilities, or fallbacks outside the approved scope.
- Treat unexpected working-tree changes as user work. Do not revert or rewrite them.
- Never commit secrets, local credentials, provider payload captures, session databases, or generated debug logs.

## 4. Repository and Toolchain Rules

### Python

- Run Python project commands through `uv`.
- Python source MUST target the version declared in `pyproject.toml`; the initial target is Python 3.13+.
- Runtime dependencies MUST have bounded declarations and an exact resolved version in `uv.lock`.
- Public functions, cross-module boundaries, configuration, protocol models, and repository results MUST be typed.
- Prefer Pydantic models for validated external data, dataclasses for internal value objects, and protocols for replaceable boundaries.
- Avoid `Any`. If unavoidable at an SDK boundary, contain it in one adapter and normalize it immediately.

### TypeScript

- The TypeScript workspace MUST use strict type checking and erasable TypeScript syntax.
- `any`, unchecked casts, and non-null assertions require a local explanation or a validated boundary.
- Direct external dependencies MUST be pinned exactly in `package.json`; the lockfile is authoritative.
- The transport-neutral SDK MUST NOT import Node-only or `pi-tui` modules.
- Generated protocol types MUST be reproducible and checked for drift.

### Bash

- Project scripts MUST be written for Bash, not an unspecified POSIX shell, PowerShell, or cmd.exe.
- Runtime shell execution MUST use the configured Bash executable and the invocation contract defined by the active design.
- Scripts MUST use safe quoting, explicit working directories, and non-zero exits on failure.
- Do not depend on interactive aliases, shell profiles, or undocumented host environment state.

## 5. Code Size and Structure

Line limits are design signals, not targets. Do not game them with dense formatting, trivial forwarding modules, or arbitrary file splits.

### Hand-written production files

- SHOULD remain between 100 and 300 physical lines when the concern warrants that size.
- At more than 300 lines, review whether protocol, persistence, rendering, parsing, or side effects can be separated.
- MUST NOT exceed 400 physical lines without a documented reason in the active design or review.
- MUST be split before exceeding 600 physical lines.

### Tests

- A test file SHOULD remain below 400 physical lines.
- A test file MUST be split by behavior before exceeding 600 physical lines.
- Shared test helpers are allowed only when they remove meaningful duplication without hiding scenario setup.

### Functions and classes

- Functions SHOULD remain below 60 physical lines.
- Functions over 100 physical lines MUST be decomposed or carry a concise explanation of why a single control flow is safer.
- Classes SHOULD remain below 200 physical lines and own one coherent responsibility.
- Constructors MUST NOT perform network calls, start processes, or mutate persistent state.

### Exclusions

Generated OpenAPI/JSON Schema clients, vendored sources, and machine-generated model catalogs are exempt from line limits. They MUST be reproducible and MUST NOT be edited manually. Migrations, fixtures, and hand-written schemas are not automatically exempt.

### Module boundaries

Prefer these separations:

- Public protocol models from internal domain models.
- Domain transitions from SQLite repositories.
- Provider request/response normalization from session orchestration.
- Tool schema and argument validation from tool side effects.
- Workspace path policy from filesystem operations.
- Process lifecycle from shell output formatting.
- UI state reduction from terminal rendering.
- Configuration parsing from credential access.

Do not create catch-all modules named `utils`, `helpers`, `common`, or `misc` when a domain-specific name exists.

## 6. Async, State, and Concurrency

- Never perform blocking filesystem, SQLite, subprocess, or SDK work directly on the event loop without a documented non-blocking boundary.
- Every background task MUST have an owner, cancellation path, terminal state, and cleanup path.
- A session MUST have at most one active run unless a future specification changes the contract.
- Client disconnection MUST NOT implicitly cancel a server-owned run.
- Cancellation MUST be idempotent and MUST terminate owned child process trees.
- State transitions and their public durable events MUST be committed atomically before publication.
- Replayed or duplicated events MUST be safe for clients to reduce idempotently.
- Mutations within one workspace MUST be serialized; read-only operations may run concurrently when safe.
- Edits MUST use preconditions and MUST never partially modify a file after a conflict.

## 7. Provider and Agent Runtime Rules

- Construct explicit Responses model classes. Do not rely on string shorthand to choose the API family.
- Provider credentials remain on the server and MUST never reach clients.
- Provider capability profiles MUST drive effective settings; endpoint naming alone is not evidence of support.
- Unsupported input modalities MUST be rejected rather than silently discarded or replaced.
- DeepSeek stateless history MUST be rebuilt from server-persisted messages without `previous_response_id`.
- Unknown provider events MUST be sanitized and diagnosed. They may be ignored only when correctness is unaffected.
- Default tests MUST use fake Responses endpoints and MUST NOT call live or paid providers.
- Live provider probes MUST be opt-in, secret-safe, and excluded from the default suite.
- Tool calls requiring approval MUST be persisted before execution. A client decision may reference only a pending server-issued approval identifier.

## 8. Configuration and Secret Handling

Use the XDG configuration root on supported macOS and Linux hosts:

```text
${XDG_CONFIG_HOME:-~/.config}/typed-code/
├── config.toml
└── credentials.toml
```

- `config.toml` stores non-sensitive settings.
- `credentials.toml` stores the typed-code server token and provider API keys.
- The configuration directory MUST use mode `0700`.
- `credentials.toml` MUST be a current-user-owned regular file with mode `0600`.
- Unsafe credential permissions MUST cause a secret-safe configuration error.
- Secrets MUST NOT be accepted through command-line flags.

Configuration precedence is intentionally file-first:

```text
config.toml / credentials.toml
    > environment variable fallback
    > non-sensitive built-in default
```

An environment variable supplies a value only when the corresponding file field is absent. Do not invert this precedence without an OpenSpec requirement and design update.

A missing provider key marks only that provider `missing_credentials`; it does not prevent service startup. A missing typed-code server token prevents authenticated API startup.

## 9. OpenSpec Development Process

Observable behavior changes require an OpenSpec change before implementation. This includes changes to:

- CLI, TUI, HTTP, SSE, protocol, session, run, provider, model, tool, approval, workspace, configuration, persistence, compaction, or error behavior.
- Prompts, user-visible messages, keyboard controls, output formatting, or recovery behavior.
- Security boundaries, supported platforms, setup, packaging, or public documentation promises.
- Any behavior covered by a canonical requirement under `openspec/specs/`.

Pure internal cleanup, typo fixes, and test-only refactors may skip a new change only when observable behavior is unchanged. When uncertain, use OpenSpec.

### Proposal phase

1. Inspect current changes and canonical specs:

   ```bash
   openspec list --json
   ```

2. Create a kebab-case change through the CLI; never create a change directory manually:

   ```bash
   openspec new change "<change-name>"
   ```

3. Read artifact status and instructions before writing each artifact:

   ```bash
   openspec status --change "<change-name>" --json
   openspec instructions <artifact-id> --change "<change-name>" --json
   ```

4. Complete the required proposal, delta specs, design, and task artifacts in dependency order.
5. Every new or changed requirement MUST have at least one `#### Scenario:` using WHEN/THEN form.
6. Resolve scope-changing questions before tasks are finalized. Deferrable tuning questions may remain in design.
7. Validate strictly:

   ```bash
   openspec validate "<change-name>" --type change --strict
   ```

Do not begin implementation until all required planning artifacts are complete and the user explicitly requests apply/implementation work.

### Apply phase

1. Re-read the proposal, design, specs, tasks, and relevant source before editing.
2. Implement tasks in dependency order; do not silently skip or broaden tasks.
3. Mark a task complete only after its observable behavior is implemented and specifically verified.
4. If implementation invalidates a design decision or requirement, update and validate the OpenSpec artifacts before continuing.
5. Keep each change focused. Do not combine broad cleanup with high-risk behavior changes unless the design makes the cleanup a prerequisite.

### Archive phase

Archive only after implementation, focused verification, quality gates, documentation, and all tasks are complete:

```bash
openspec validate "<change-name>" --type change --strict
openspec archive "<change-name>" -y
openspec validate --specs --strict
```

After archive, confirm the canonical specs express the delivered behavior.

## 10. Testing Standards

Tests defend observable contracts, not implementation structure.

### Required test layers

- **Unit tests:** domain transitions, provider capability resolution, path policy, truncation, event reduction, and pure formatting.
- **Repository tests:** migrations, transactions, rollback, sequence/revision monotonicity, snapshots, replay, and recovery.
- **Provider conformance tests:** fake Responses endpoints for text, SSE, thinking, function calls/results, usage, failures, unknown events, and unsupported settings.
- **API integration tests:** authenticated commands, validation, conflicts, approvals, cancellation, SSE reconnect/replay, reset, and restart.
- **Contract tests:** OpenAPI and event-schema generation plus TypeScript decoding/reducer compatibility.
- **TUI tests:** virtual-terminal rendering, streaming updates, resize, approvals, reconnect, abort, and terminal cleanup.
- **Live smoke tests:** opt-in only for configured DeepSeek and CLIProxyAPI endpoints.

### Test rules

- Every OpenSpec scenario MUST map to an automated test or an explicit deterministic verification step.
- Every bug fix MUST first have a reproduction and then a regression test that fails for the plausible bug.
- Prefer fakes at network, clock, filesystem, process, and provider boundaries over mocks of internal methods.
- Tests MUST be deterministic, isolated, order-independent, and safe to run in parallel unless explicitly marked otherwise.
- Do not use real home directories, user configuration, provider credentials, network endpoints, or unbounded subprocesses in default tests.
- Avoid sleeps and timing-sensitive assertions. Use controlled clocks, events, and bounded timeouts.
- Assert public outcomes, state transitions, persisted records, emitted events, and side effects. Do not test source text or private call order.
- Snapshot tests are appropriate only for stable public protocol/rendering output and MUST be reviewed as contracts.
- Test tool failures and cancellation paths, not only success paths.

### Verification order

1. Reproduce the behavior or failure.
2. Run the smallest relevant unit or integration test during iteration.
3. Run all tests in the affected package.
4. Run cross-language contract checks when protocol artifacts change.
5. Run project quality gates.
6. Perform the applicable end-to-end smoke scenario.

Do not claim broader verification than was actually executed.

## 11. Quality Gates

The repository must expose stable top-level commands as the Python and TypeScript workspaces are introduced.

Expected Python checks:

```bash
uv run ruff check src tests
uv run ty check src tests
uv run pytest -q
```

Expected TypeScript checks:

```bash
npm run check
npm run test:unit
```

Protocol changes additionally run the checked contract-generation command defined by the workspace. OpenSpec changes additionally run strict validation.

During development, run focused tests first. Before declaring a non-trivial change complete, run every applicable gate above. Do not add suppressions, broad excludes, or downgraded strictness to make a gate pass.

If a command has not yet been introduced, the change that introduces its language workspace MUST add the command before relying on it as a gate.

## 12. Dependencies and Supply Chain

- Treat dependency and lockfile changes as code changes requiring review.
- Prefer standard-library or existing dependencies when they satisfy the contract clearly.
- New dependencies require a concrete need, maintenance assessment, license check, and security review.
- Do not add overlapping libraries for HTTP, validation, terminal rendering, testing, or configuration without replacing the old choice.
- Install dependencies without unreviewed lifecycle scripts.
- Generated lockfile changes MUST be included and verified with the manifest change that caused them.
- Never downgrade type safety or remove behavior to accommodate an outdated dependency; resolve the dependency issue deliberately.

## 13. Errors, Logging, and Security

- Public errors MUST use stable codes and sanitized messages.
- Preserve internal causes for diagnostics without exposing secrets or raw provider bodies to clients.
- Never log authorization headers, API keys, server tokens, complete credential files, or unrestricted environment variables.
- Validate all client data at the API boundary and all provider data at the runtime adapter boundary.
- A client approval is not authorization. Re-check authenticated session, run, workspace, and tool policy before side effects.
- Loopback binding is not a complete security boundary; authenticated non-health routes remain mandatory.
- Workspace confinement is not a sandbox. Document the server’s OS-level authority accurately.
- Avoid broad `except Exception` handlers except at process, task, API, or SDK boundaries where unknown failures are converted into terminal sanitized state.

## 14. Documentation and User-Visible Changes

- Documentation, OpenSpec contracts, examples, and runtime behavior MUST agree.
- Do not document unimplemented or unverified behavior as available.
- Setup examples MUST avoid literal secrets and unsafe file permissions.
- Platform support statements MUST explicitly say macOS/Linux with Bash for the MVP and MUST NOT imply native Windows/PowerShell support.
- Public protocol changes require updated client examples and contract artifacts.
- Significant user-facing behavior changes require an appropriate changelog entry once a changelog exists.

## 15. Git and Collaboration

- Do not commit, tag, push, or open a pull request unless the user explicitly asks.
- Never use destructive commands such as `git reset --hard`, `git clean -fd`, or force push.
- Do not stash or rewrite unrelated user changes.
- Stage and commit only explicit files changed for the requested work.
- Keep commits focused and use concise imperative messages once commits are requested.
- Before committing, verify affected tests, quality gates, OpenSpec status, and the exact staged paths.

## 16. Definition of Done

A change is complete only when:

- Every approved OpenSpec task and requirement is implemented.
- Every affected caller, protocol client, test, and document is updated.
- Focused tests and applicable project quality gates pass.
- The changed behavior is exercised end to end using the appropriate smoke path.
- Errors, cancellation, security, and recovery paths are verified where applicable.
- No obsolete compatibility path, dead code, placeholder, TODO, fake fallback, or stale artifact remains.
- OpenSpec strict validation passes, and archive is performed only when explicitly requested after delivery.

“Compiles,” “the focused test passes,” and “the scaffold exists” are not sufficient completion criteria.
