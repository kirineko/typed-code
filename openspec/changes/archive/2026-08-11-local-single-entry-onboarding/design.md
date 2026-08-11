## Context

See `proposal.md` for motivation. The MVP already ships:

- Python `typed-code serve` with XDG `config.toml` / `credentials.toml`, bearer auth, health/models/sessions/SSE.
- TypeScript `@typed-code/cli` that **requires** `--token` / `TYPED_CODE_SERVER_TOKEN` and assumes an external server.
- Provider profiles with outdated fixed budgets (`deepseek` 100k, cliproxy 128k).

Constraints that remain binding:

- Responses-only execution; provider credentials must never be returned to API clients.
- File-first XDG config; credentials directory `0700`, file `0600`.
- Loopback-default service; one active run per session.
- CLI must not embed agent execution or call providers directly for turns.

## Goals / Non-Goals

**Goals:**

- Ordinary users run one command, configure keys once, and chat.
- Hide server token and base URL from default UX while keeping them on the wire for the local API.
- Hot-reload credentials after `/config` without full process restart when possible.
- Idle session model switch via `/model` with model-scoped context budgets (DeepSeek 1M, OpenAI-via-CLIProxy 272k, else 128k).

**Non-Goals:**

- Official OpenAI direct provider (still DeepSeek + CLIProxy only).
- Auto-start on non-loopback or multi-user hosts.
- Web/desktop packaging or unified single binary beyond CLI-spawned Python.
- Live provider probes on every startup.
- Windows/PowerShell support.
- Changing approval policy or tool set.

## Decisions

### 1. TypeScript CLI is the default single entry

**Choice:** Node/`typed-code-cli` (package bin may also be aliased as `typed-code` in docs/npm) owns:

1. Ensure XDG dir + credentials (generate `server_token` if missing).
2. Onboarding if no provider keys.
3. Health probe → spawn `uv run typed-code serve` (or configured Python entry) if needed.
4. TUI + slash commands.
5. Kill **owned** child serve on exit.

**Alternatives:** Python as parent spawning Node TUI (worse fit for pi-tui); pure wrapper script (weaker product surface).

**Rationale:** TUI and slash UX live in TS; lifecycle ownership is clearer when the process users interact with is the parent.

### 2. Server token automation

**Choice:** On first run, generate a high-entropy token, write `server_token` into `credentials.toml` (0600). CLI and child serve both load via existing file-first credential loader (CLI reads token for HTTP; serve validates bearer).

**Precedence:** Explicit `--token` / env still override for advanced users; default path never prompts.

**Alternative:** OS keychain — deferred; XDG file matches existing design.

### 3. Provider key onboarding gate

```text
has_any_key = deepseek_api_key OR cliproxy_api_key
if not has_any_key → blocking onboarding
else → main UI (missing second provider is OK)
```

No live API validation at startup. Optional “Test connection” may live under `/config` later; not required for MVP of this change.

### 4. Hot reload API

**Choice:** Authenticated endpoint, e.g. `POST /v1/config/reload` (exact path in implementation), that:

1. Re-reads `config.toml` + `credentials.toml` with permission checks.
2. On **failure**: keep previous in-memory credentials/settings; return structured error.
3. On **success**: replace credential object, refresh provider availability, `refresh_cliproxy` if key present.
4. Never echoes secrets.

**CLI flow after `/config` save:** write files → call reload → refresh health/models UI.

**Alternative:** Restart child serve on every save — simpler but slower and drops in-flight runs; use only if reload proves unsafe. Prefer in-process reload; if an in-flight run is active, reload credentials for **future** runs but do not cancel the active run unless credentials for its provider disappear (then surface a clear notice; do not auto-abort without user action).

### 5. Idle session model switch

**Choice:** `POST /v1/sessions/{id}` patch or dedicated `POST /v1/sessions/{id}/model` with `{ provider, model }`, allowed only when `phase == idle`. Persist + emit durable event (e.g. `session.model_changed` or system notice + snapshot fields). Reject non-idle with conflict.

**CLI `/model`:** list from `GET /v1/models` with context budgets; call switch API; `applySnapshot`.

### 6. Context budget rules

| Rule | Budget |
|------|--------|
| Provider `deepseek` | 1_000_000 |
| CLIProxy model id matches OpenAI GPT-family (`gpt-` prefix or known gpt-5.* catalog) | 272_000 |
| Else | 128_000 |

Expose budget on `ModelInfo` (and session snapshot if useful). Compaction threshold remains a fraction of **current** budget (existing ~90% style). Update `ProviderProfile.context_token_budget` construction to be model-aware rather than a single cliproxy constant.

**Note:** 272k for OpenAI-family is a product choice (aligns with common long-context pricing threshold mental model); not a claim that the provider hard-caps at 272k.

### 7. Slash command routing

**Choice:** Pure client-side in composer `onSubmit`:

- Trim; if starts with `/`, parse command + args; never `createTurn`.
- `/config`, `/model`, `/help` in this change.
- Unknown → error + help text.

### 8. Child process spawn details

**Choice:** Spawn via `uv run typed-code serve --host 127.0.0.1 --port <port>` with env inheriting `XDG_CONFIG_HOME` / token files already written. Wait for `/v1/health` with protocol match and bounded timeout. Track child PID; on CLI exit SIGTERM then SIGKILL after grace.

Port: default 8741; if occupied by **compatible** service with same token, reuse; if occupied by **incompatible** or unauthenticated stranger, fail with clear error (do not steal port).

### 9. Credential writes from CLI

**Choice:** CLI may write `credentials.toml` and `config.toml` for onboarding/`/config`. This slightly softens “only server touches secrets” to “only server **uses** secrets for providers; CLI may **setup-write** local files.” Provider keys still never sent to remote typed-code peers or logged.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Spawn fails (`uv`/Python missing) | Clear error: install Python deps / run advanced serve path |
| Hot reload races with active run | Reload applies to new runs; document; no silent abort |
| Port conflict with non-typed-code process | Explicit error; optional `--port` advanced flag |
| CLI writing secrets increases attack surface | 0600 enforcement; refuse unsafe modes; no secret echo |
| GPT-family detection false positives/negatives | Prefer `gpt-` prefix + known list; unknown → 128k |
| Previous docs teach `--token` | README default path rewrite; keep advanced section |

## Migration Plan

1. Ship code behind same packages; default CLI behavior becomes single-entry.
2. Existing users with credentials keep working; missing server token is auto-filled on next launch.
3. Users who only used env vars without files: first launch may write file from env-resolved values when generating token (do not strip env-only provider keys).
4. No database migration required beyond optional event type for model change.
5. Rollback: advanced `serve` + `--token` path remains.

## Open Questions

None that block specs or tasks. Deferrable polish: optional `/config` connection test; npm global bin name `typed-code` vs `typed-code-cli` branding.
