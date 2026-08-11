# typed-code

A typed coding agent harness with a Python agent service and TypeScript CLI.

## Requirements

- **Python 3.13+** and [uv](https://docs.astral.sh/uv/)
- **Node.js 22+**
- **macOS or Linux with Bash** (MVP)

Native Windows / PowerShell are out of scope for the MVP.

## Setup

```bash
uv sync
npm install
npm run build -w @typed-code/cli
```

## Default path (single entry)

One command is enough for ordinary local use:

```bash
npx typed-code-cli --workspace "$PWD"
# or: node packages/cli/dist/bin.js
```

What happens:

1. Ensures `~/.config/typed-code/credentials.toml` (dir `0700`, file `0600`)
2. **Auto-generates** a server bearer token (never shown in the TUI)
3. Starts or reuses the compatible loopback agent service
4. Runs secure provider setup inside the TUI when no provider is available
5. Opens an unsaved new-session draft for the canonical workspace
6. Persists the session only after the first non-empty prompt

Historical sessions are never selected automatically. Use `/resume` to return to current-project history or `/resume --all` to browse canonical workspace groups.

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

## Advanced: two-process mode

```bash
# terminal A
export TYPED_CODE_SERVER_TOKEN=…
uv run typed-code serve

# terminal B
npx typed-code-cli --no-spawn --token "$TYPED_CODE_SERVER_TOKEN" --new
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
