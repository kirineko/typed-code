## 1. Context budgets and public model metadata

- [x] 1.1 Define model-scoped context budget resolution (DeepSeek 1_000_000, OpenAI-family via CLIProxy 272_000, unknown 128_000) in the provider profile/catalog layer.
- [x] 1.2 Expose `context_token_budget` (or equivalent) on public model list entries and wire session/runtime compaction to the **current** model budget.
- [x] 1.3 Add unit tests for budget classification and compaction using the selected model’s budget after a model identity change.

## 2. Service: reload and idle model switch

- [x] 2.1 Implement authenticated config/credentials reload that re-reads XDG files, enforces 0700/0600 rules, rejects unsafe/invalid updates while keeping prior credentials, refreshes provider availability and CLIProxy discovery, and never returns secrets.
- [x] 2.2 Implement idle-only session provider/model update with validation, persistence, revision bump, durable event or equivalent snapshot-visible change, and conflict errors when not idle.
- [x] 2.3 Add API integration tests for reload success/failure, secret-safe responses, model switch idle/non-idle/unavailable cases, and models list budget fields.
- [x] 2.4 Export updated OpenAPI/contract artifacts and keep TypeScript protocol types in sync.

## 3. CLI: credentials, single entry, service lifecycle

- [x] 3.1 Add XDG config/credentials read-write helpers in the CLI (create dir 0700, credentials 0600, generate server_token when missing, detect any provider key).
- [x] 3.2 Implement first-run provider key onboarding when no provider key exists; skip when any key exists; persist keys safely.
- [x] 3.3 Implement local service ensure logic: probe health/protocol, reuse compatible loopback service, otherwise spawn `typed-code serve`, wait until ready, track ownership.
- [x] 3.4 On CLI exit, stop only the service process this entry spawned; never kill a reused external service; restore terminal state.
- [x] 3.5 Make default CLI entry work without required `--token`; keep advanced token/base-url flags for power users.

## 4. CLI: slash commands and UI

- [x] 4.1 Intercept composer submissions starting with `/` so they never call `createTurn`; implement `/help` listing supported commands.
- [x] 4.2 Implement `/config` menu to view provider availability and set/replace DeepSeek and CLIProxy keys (and defaults as needed), write files, call reload, refresh UI without showing server_token values.
- [x] 4.3 Implement `/model` picker from service models (show context budgets); switch current session when idle; refuse with a clear message when not idle.
- [x] 4.4 Update status bar to show usage against the **selected model’s** context budget when usage is available.

## 5. Documentation and verification

- [x] 5.1 Rewrite README default path as single-entry local use; document onboarding, `/config`, `/model`, context budget rules; keep advanced two-process/`serve` section.
- [x] 5.2 Add focused CLI tests for onboarding skip/run, slash routing (no createTurn), and lifecycle ownership mocks.
- [x] 5.3 Run Python and TypeScript quality gates plus strict OpenSpec validation for this change.
