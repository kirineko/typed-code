/** CLI configuration from flags + env (provider secrets via XDG credentials). */

export interface CliFlags {
  baseUrl: string;
  /** Empty until resolved from file/env/flag. */
  token: string;
  workspace: string;
  sessionId?: string | undefined;
  provider?: "deepseek" | "cliproxy" | undefined;
  model?: string | undefined;
  createNew: boolean;
  help: boolean;
  /** Skip auto-spawn; only connect to existing service. */
  noSpawn: boolean;
}

export function parseArgs(argv: string[]): CliFlags {
  const env = process.env;
  let baseUrl = env.TYPED_CODE_BASE_URL ?? "http://127.0.0.1:8741";
  let token = env.TYPED_CODE_SERVER_TOKEN ?? "";
  let workspace = env.TYPED_CODE_WORKSPACE ?? process.cwd();
  let sessionId: string | undefined;
  let provider: "deepseek" | "cliproxy" | undefined;
  let model: string | undefined;
  let createNew = false;
  let help = false;
  let noSpawn = false;

  for (let i = 0; i < argv.length; i++) {
    const a = argv[i] ?? "";
    const next = () => {
      const v = argv[++i];
      if (v === undefined) {
        throw new Error(`missing value for ${a}`);
      }
      return v;
    };
    switch (a) {
      case "-h":
      case "--help":
        help = true;
        break;
      case "--base-url":
        baseUrl = next();
        break;
      case "--token":
        token = next();
        break;
      case "--workspace":
        workspace = next();
        break;
      case "--session-id":
        sessionId = next();
        break;
      case "--provider": {
        const p = next();
        if (p !== "deepseek" && p !== "cliproxy") {
          throw new Error(`invalid provider: ${p}`);
        }
        provider = p;
        break;
      }
      case "--model":
        model = next();
        break;
      case "--new":
        createNew = true;
        break;
      case "--no-spawn":
        noSpawn = true;
        break;
      default:
        if (a.startsWith("-")) {
          throw new Error(`unknown flag: ${a}`);
        }
        throw new Error(`unexpected argument: ${a}`);
    }
  }

  return {
    baseUrl: baseUrl.replace(/\/+$/, ""),
    token,
    workspace,
    sessionId,
    provider,
    model,
    createNew,
    help,
    noSpawn,
  };
}

export function helpText(): string {
  return `typed-code-cli — local coding agent (single entry)

Usage:
  typed-code-cli [options]

Default path:
  - Loads/creates ~/.config/typed-code/credentials.toml (server token auto)
  - Prompts for a provider key on first run if none is configured
  - Starts local typed-code serve when needed
  - Opens interactive TUI

Options:
  --workspace <path>     Workspace for new sessions (default: cwd)
  --session-id <id>      Resume an existing session
  --new                  Create a new session
  --provider <name>      deepseek | cliproxy
  --model <id>           Model id
  --base-url <url>       Advanced: service URL (default http://127.0.0.1:8741)
  --token <token>        Advanced: server bearer (default: credentials.toml)
  --no-spawn             Advanced: do not auto-start serve
  -h, --help             Show help

In-chat commands:
  /help                  List commands
  /config                Configure provider API keys (hot-reload)
  /model                 Switch model (idle session)

Keys:
  Enter                  Submit prompt (when idle)
  Ctrl+D / Esc           Abort active run
  y / n                  Approve / reject pending approval
  Ctrl+C                 Quit
  ?                      Toggle help in status

Context budgets: DeepSeek 1M · OpenAI-via-CLIProxy 272k · other 128k
`;
}

export function validateFlags(flags: CliFlags): string | null {
  if (flags.help) {
    return null;
  }
  // Token may be filled later from credentials.toml
  if (!flags.baseUrl) {
    return "missing --base-url";
  }
  return null;
}
