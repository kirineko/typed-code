## Why

The MVP correctly separates a Python agent service from a TypeScript CLI, but ordinary users must manually start the server, configure a server bearer token, and pass that token into the CLI before they can chat. That dual-process, dual-token setup is an implementation boundary, not a product feature. Users only care about provider API keys and which model they are using. Now that the core service, tools, and CLI shell exist, the next product step is a single local entry that hides process plumbing, guides first-run key setup, and exposes in-session `/config` and `/model` commands with model-accurate context budgets.

## What Changes

- Make the TypeScript CLI the **default single entry** for local use: ensure a loopback agent service is available (spawn or reuse), inject a locally stored server token automatically, and open the interactive TUI without requiring `--token` for normal users.
- **Hide server bearer tokens and service base URLs** from the default UX; generate and persist `server_token` under XDG `credentials.toml` with safe permissions when missing.
- On startup, if **no provider key** is configured (neither DeepSeek nor CLIProxy), run a blocking onboarding flow that collects at least one key and writes `credentials.toml`. If **any** provider key exists, skip key onboarding.
- Add client-side slash commands:
  - `/config` — configure or reconfigure providers and keys; update defaults; **hot-reload** credentials into the running service.
  - `/model` — select provider/model while idle; show each model’s context budget; apply the selection to the **current session** when idle.
- Align model context budgets used for compaction and status display:
  - DeepSeek models: **1_000_000** tokens.
  - OpenAI-family models exposed via CLIProxy (e.g. `gpt-5.*`): **272_000** tokens.
  - Unknown models: **128_000** tokens (conservative default).
- Add a minimal authenticated **config reload** path on the service so credential and default changes take effect without a full process restart when the CLI owns the local server.
- Keep advanced explicit `typed-code serve` and env-based configuration for power users; demote them in user docs.

## Capabilities

### New Capabilities

- `local-onboarding`: First-run provider-key setup, automatic server-token lifecycle, single-entry process ownership (spawn/reuse/stop local serve), and slash-command configuration UX contracts for ordinary local users.

### Modified Capabilities

- `cli-client`: Default entry no longer requires manual token flags; slash commands `/config` and `/model`; optional automatic local service lifecycle.
- `agent-service`: Authenticated config/credentials reload; optional session model switch while idle; health/models reflect reloaded provider availability.
- `agent-runtime`: Context token budgets follow provider/model rules (DeepSeek 1M, OpenAI-via-CLIProxy 272k, unknown 128k) for compaction and effective settings.

## Impact

- TypeScript CLI gains service lifecycle, XDG credential write paths, onboarding UI, and slash-command routing before `createTurn`.
- Python service gains a small authenticated reload (and possibly session model-update) API; credential loading becomes reloadable without dropping the process.
- Provider profiles and public model metadata expose accurate `context_token_budget` values used by compaction and CLI status.
- Documentation shifts the default path to single-entry local use; two-process setup remains advanced.
- Security model remains loopback + bearer token + file modes `0700`/`0600`; tokens are automated, not removed from the wire protocol.
- No change to Responses-only execution, workspace tools policy, or macOS/Linux Bash platform scope. Native Windows remains out of scope.
