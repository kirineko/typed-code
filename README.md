# typed-code

A typed coding agent harness with a Python agent service and TypeScript CLI.

## Requirements

- **Production:** macOS on Apple Silicon and Node.js 22+. The packaged service does not require Python or `uv`.
- **Development:** Python 3.13+, [uv](https://docs.astral.sh/uv/), Node.js 22+, and Bash.

Linux remains supported for source development but does not yet have a verified production companion. Other production platforms fail before the TUI with the detected platform and supported target.

## Production installation (macOS Apple Silicon)

Install the published CLI package. Its same-version optional dependency provides the signed and notarized service companion:

```bash
npm install --global @typed-code/cli
typed-code
```

`typed-code` is the only public command. The former `typed-code-cli` npm bin was removed; scripts must switch to `typed-code`. Upgrades preserve the existing XDG credentials and SQLite database, but a running older service must be stopped before installing an incompatible CLI release.

## Development setup

```bash
uv sync
npm install
npm run dev:link
typed-code dev configure --project "$(pwd -P)"
```

The one-time development configuration stores the absolute backend source root
under `${XDG_CONFIG_HOME:-~/.config}/typed-code/config.toml`. Afterward the linked
CLI is cwd-independent:

```bash
cd /path/to/any-project
typed-code

# Equivalent direct backend entry while staying in the target workspace:
uv run --project /absolute/path/to/typed-code typed-code serve
```

## Default path (single entry)

One command is enough for ordinary local use:

```bash
typed-code
```

What happens:

1. Ensures `~/.config/typed-code/credentials.toml` (dir `0700`, file `0600`)
2. **Auto-generates** a server bearer token (never shown in the TUI)
3. Starts or reuses the compatible persistent user-scoped loopback service
4. Runs secure provider setup inside the TUI when no provider is available
5. Opens an unsaved new-session draft for the canonical workspace
6. Persists the session only after the first non-empty prompt

Historical sessions are never selected automatically. Use `/resume` to return to current-project history or `/resume --all` to browse canonical workspace groups.

### Service management

Service commands run without opening the TUI:

| Command | Behavior |
|---------|----------|
| `typed-code server status` | Probe authenticated health without starting an absent service |
| `typed-code server start` | Start or reuse the matching user-scoped service |
| `typed-code server stop` | Stop only when no run or approval is active |
| `typed-code server stop --force` | Explicitly interrupt active work and stop |
| `typed-code server restart [--force]` | Apply the same guard, then start the matching service |
| `typed-code server logs [--lines N]` | Show bounded service logs with known credentials redacted |

The service persists after all CLI clients exit. Optional idle shutdown is disabled by default. To enable it, add:

```toml
[service]
idle_timeout_seconds = 900
```

`TYPED_CODE_IDLE_TIMEOUT_SECONDS` is the environment fallback. `0` disables the policy. Idle shutdown never fires while a run, approval, or event stream is active.

Startup model precedence is: explicit `--provider`/`--model`, the most recent successful `/model` selection, `deepseek/deepseek-v4-flash` when DeepSeek is available, the service default, then the first available model. This means a fresh setup with both provider credentials prefers DeepSeek, while a later user selection such as `cliproxy/gpt-5.6-terra` is restored on the next launch. The `/model` flow uses each provider's declared Responses API effort table: DeepSeek offers `none`/`low`/`high`/`max` and defaults to `high`; OpenAI reasoning models offer `none`/`low`/`medium`/`high`/`xhigh`/`max` and default to `medium`. The selected effort appears in the header and `/status`, persists for the next launch, and is sent unchanged with each future turn. Models without declared reasoning support receive no inferred setting.

### In-chat commands

| Command | Purpose |
|---------|---------|
| `/help` | Show command help |
| `/config [deepseek\|cliproxy]` | Set or replace a provider key and hot-reload the service |
| `/model [provider/model]` | Select a model, then choose its supported thinking intensity |
| `/new` | Return to an unsaved draft for the launch workspace |
| `/resume [session-prefix]` | Resume current-project history |
| `/resume --all` | Browse sessions grouped by canonical workspace |
| `/status` | Show session, connection, model, and confirmed usage details |
| `/abort` | Cancel the active run |
| `/keys` | Show keyboard controls |
| `/quit` | Exit without cancelling a server-owned run |

Slash commands and their model/session/provider arguments are completed in the composer.

### Context budgets (compaction + status)

| Models | Budget |
|--------|--------|
| DeepSeek (`deepseek-v4-flash`, …) | **1_000_000** |
| OpenAI-family via CLIProxy (`gpt-*`, …) | **272_000** |
| Other / unknown | **128_000** |

The footer shows provider-confirmed input, output, and total usage against the selected model budget. While a new turn runs, it retains the previous confirmed value and marks current usage pending; it does not estimate live tokens from text length.

### Keys (no flags needed)
| Key | Action |
|-----|--------|
| `Enter` | Submit |
| `Alt+Enter`, `Shift+Enter`, or `Ctrl+Enter` | Insert newline |
| `Tab` | Complete slash commands, arguments, and paths |
| `Ctrl+End` | Follow latest streamed output |
| `Ctrl+T` | Select a completed thinking block; press again to collapse the expanded block |
| `Esc` or `Ctrl+D` | Abort an active run |
| `y` / `n` | Approve or reject a pending tool call |
| `Ctrl+L` | Redraw |
| `Ctrl+C` | Quit without cancelling a server-owned run |

### Credentials


Stored in:

```text
${XDG_CONFIG_HOME:-~/.config}/typed-code/
├── config.toml          # optional non-secret service settings
├── preferences.toml     # most recently selected provider/model (0600)
└── credentials.toml     # server_token + provider keys (0600)
```

| Field | Env fallback |
|-------|----------------|
| `server_token` | `TYPED_CODE_SERVER_TOKEN` (auto if missing) |
| `deepseek_api_key` | `DEEPSEEK_API_KEY` |
| `cliproxy_api_key` | `CLIPROXY_API_KEY` |

File fields win over environment variables.

Any **one** provider key is enough to skip onboarding; the other can stay missing.

### Data, backup, and runtime cleanup

Durable state lives under `${XDG_DATA_HOME:-~/.local/share}/typed-code/`:

```text
typed-code/
├── typed-code.db         # sessions, transcript, and event history
└── runtime/              # disposable lock, descriptor, and bounded logs
```

Back up `typed-code.db` together with the XDG configuration directory. `runtime/` is process metadata, not durable state. Delete it only after `typed-code server stop`; a live lock/descriptor must not be removed to work around a startup error.

### Troubleshooting

- **Incompatible or legacy service:** run the matching installed `typed-code server stop`, then reinstall/upgrade and start again. The launcher never attaches to a mismatched release or protocol.
- **Port already in use:** stop the conflicting process or choose one fixed `[listen]` port in `config.toml`. The launcher does not silently choose a random port.
- **Stale development path:** rerun `typed-code dev configure --project <absolute-root>` or `--executable <absolute-path>`. The target workspace is never treated as the backend source.
- **Active-work stop refused:** resume the session and finish/abort it, or use `server stop --force` only when interruption is intended.
- **Unsupported production target:** use source development or a separately versioned preview. The production launcher does not search `PATH` for an arbitrary backend.
- **Runtime metadata appears stale:** use `server status` first. Identity is accepted only when descriptor data matches authenticated health; do not signal a descriptor PID directly.

## Advanced: two-process mode

```bash
# terminal A — explicit cwd-independent development service
export TYPED_CODE_SERVER_TOKEN=…
uv run --project /absolute/path/to/typed-code typed-code serve

# terminal B — externally managed endpoint
typed-code --no-spawn --token "$TYPED_CODE_SERVER_TOKEN" --new
```

Other flags: `--base-url`, `--session-id`, `--provider`, `--model`.

## Quality gates

```bash
uv run ruff check src tests
uv run ty check src tests
uv run pytest -q
npm run check
npm run test:unit
```

## Opt-in live smoke

```bash
uv run typed-code smoke deepseek
uv run typed-code smoke cliproxy
```

Not part of the default test suite; never prints API keys.

## Contracts

```bash
uv run typed-code export-contracts
```

Writes `contracts/openapi.v1.json` and `contracts/events.schema.v1.json`.
