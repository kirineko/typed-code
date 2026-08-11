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
npx typed-code-cli --new --workspace "$PWD"
# or: node packages/cli/dist/bin.js --new
```

What happens:

1. Ensures `~/.config/typed-code/credentials.toml` (dir `0700`, file `0600`)
2. **Auto-generates** a server bearer token (never shown in the TUI)
3. If **no** provider key exists, runs first-run setup (DeepSeek **or** CLIProxy)
4. Starts `uv run typed-code serve` on loopback when needed (reuses a compatible server)
5. Opens the interactive TUI

### In-chat commands

| Command | Purpose |
|---------|---------|
| `/help` | List commands |
| `/config` | Set/replace DeepSeek or CLIProxy API keys; **hot-reloads** the service |
| `/model` | Switch model for the **idle** current session (shows context budget) |

### Context budgets (compaction + status)

| Models | Budget |
|--------|--------|
| DeepSeek (`deepseek-v4-flash`, …) | **1_000_000** |
| OpenAI-family via CLIProxy (`gpt-*`, …) | **272_000** |
| Other / unknown | **128_000** |

Status bar shows `tokens≈used/budget` when usage is known.

### Keys (no flags needed)

Stored in:

```text
${XDG_CONFIG_HOME:-~/.config}/typed-code/
├── config.toml          # optional non-secret settings
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
