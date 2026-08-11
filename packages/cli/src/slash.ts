/**
 * Client-side slash command routing (never becomes a model turn).
 *
 * Important: while pi-tui is running we MUST NOT use node:readline or
 * stop/start the TUI for menus — that breaks raw mode and leaves the
 * terminal unable to accept editor input after the menu exits.
 *
 * All /config and /model actions are therefore non-interactive argument forms.
 */

import type { TypedCodeClient } from "@typed-code/sdk";
import {
  credentialsPath,
  mergeProviderKeys,
  readCredentialsFile,
  writeCredentialsFile,
  type LocalCredentials,
} from "./local-config.js";
import type { SessionController } from "./session-controller.js";

export function isSlashCommand(text: string): boolean {
  return text.trimStart().startsWith("/");
}

/** Credential configuration commands must never be retained in editor history. */
export function shouldRecordInHistory(text: string): boolean {
  return !/^\s*\/config(?:\s|$)/i.test(text);
}

export function parseSlash(text: string): { command: string; args: string } {
  const trimmed = text.trim();
  const space = trimmed.indexOf(" ");
  if (space === -1) {
    return { command: trimmed.toLowerCase(), args: "" };
  }
  return {
    command: trimmed.slice(0, space).toLowerCase(),
    args: trimmed.slice(space + 1).trim(),
  };
}

export function slashHelpText(): string {
  return [
    "commands:",
    "  /help",
    "  /config show",
    "  /config deepseek",
    "  /config cliproxy",
    "  /model",
    "  /model <n>",
    "  /model <provider> <model-id>",
  ].join("\n");
}

export async function handleSlashCommand(opts: {
  text: string;
  client: TypedCodeClient;
  controller: SessionController;
  creds: LocalCredentials;
  onCreds: (c: LocalCredentials) => void;
  setNotice: (msg: string) => void;
  promptProviderKey: (
    provider: "deepseek" | "cliproxy",
  ) => Promise<string | null>;
}): Promise<void> {
  const { command, args } = parseSlash(opts.text);
  switch (command) {
    case "/help":
    case "/?":
      opts.setNotice(slashHelpText().replace(/\n/g, " · "));
      return;
    case "/config":
      await runConfigCommand(opts, args);
      return;
    case "/model":
      await runModelCommand(opts, args);
      return;
    default:
      opts.setNotice(`unknown command ${command} — try /help`);
  }
}

async function runConfigCommand(
  opts: {
    client: TypedCodeClient;
    creds: LocalCredentials;
    onCreds: (c: LocalCredentials) => void;
    setNotice: (msg: string) => void;
    promptProviderKey: (
      provider: "deepseek" | "cliproxy",
    ) => Promise<string | null>;
  },
  args: string,
): Promise<void> {
  const parts = args.split(/\s+/).filter(Boolean);

  if (parts.length === 0 || parts[0] === "show") {
    opts.setNotice(
      `keys · deepseek=${opts.creds.deepseek_api_key ? "set" : "missing"} · cliproxy=${opts.creds.cliproxy_api_key ? "set" : "missing"} · set with: /config deepseek | /config cliproxy`,
    );
    return;
  }

  if (parts[0] === "deepseek" || parts[0] === "cliproxy") {
    const provider = parts[0];
    if (parts.length > 1) {
      opts.setNotice(
        `API keys cannot be entered in the composer · use /config ${provider}`,
      );
      return;
    }
    const key = await opts.promptProviderKey(provider);
    if (!key?.trim()) {
      opts.setNotice("config cancelled");
      return;
    }
    await applyKeyPatch(opts, provider, key.trim());
    return;
  }

  opts.setNotice(
    "usage: /config show | /config deepseek | /config cliproxy",
  );
}

async function applyKeyPatch(
  opts: {
    client: TypedCodeClient;
    creds: LocalCredentials;
    onCreds: (c: LocalCredentials) => void;
    setNotice: (msg: string) => void;
  },
  provider: "deepseek" | "cliproxy",
  key: string,
): Promise<void> {
  const patch =
    provider === "deepseek"
      ? { deepseek_api_key: key }
      : { cliproxy_api_key: key };
  const next = mergeProviderKeys(opts.creds, patch);
  writeCredentialsFile(credentialsPath(), next);
  opts.onCreds(next);

  // Bounded reload so a hung HTTP call cannot freeze the TUI forever.
  try {
    const reloaded = await Promise.race([
      opts.client.reloadConfig(),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("reload timed out after 8s")), 8000),
      ),
    ]);
    const p = reloaded.providers;
    opts.setNotice(
      `config saved · deepseek=${p.deepseek ?? "?"} cliproxy=${p.cliproxy ?? "?"}`,
    );
  } catch (err) {
    opts.setNotice(
      `config saved to disk · reload: ${err instanceof Error ? err.message : String(err)} · restart CLI if models look stale`,
    );
  }
}

async function runModelCommand(
  opts: {
    client: TypedCodeClient;
    controller: SessionController;
    setNotice: (msg: string) => void;
  },
  args: string,
): Promise<void> {
  if (opts.controller.view.phase !== "idle") {
    opts.setNotice(`cannot switch model while phase=${opts.controller.view.phase}`);
    return;
  }
  if (!opts.controller.sessionId) {
    opts.setNotice("no session attached");
    return;
  }

  let listed;
  try {
    listed = await Promise.race([
      opts.client.listModels({ refresh: true }),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("list models timed out")), 10000),
      ),
    ]);
  } catch (err) {
    opts.setNotice(
      `list models failed: ${err instanceof Error ? err.message : String(err)}`,
    );
    return;
  }

  const models = listed.models.filter((m) => m.availability === "available");
  if (models.length === 0) {
    opts.setNotice("no available models — use /config deepseek or /config cliproxy");
    return;
  }

  const parts = args.split(/\s+/).filter(Boolean);

  // /model  (list in status — no interactive menu)
  if (parts.length === 0) {
    const lines = models.slice(0, 12).map((m, i) => {
      const budget = m.context_token_budget ?? "?";
      return `[${i}] ${m.provider}/${m.model_id} ctx=${budget}`;
    });
    const more = models.length > 12 ? ` · +${models.length - 12} more` : "";
    opts.setNotice(
      `models · ${lines.join(" · ")}${more} · pick: /model <n> or /model <provider> <id>`,
    );
    return;
  }

  // /model deepseek deepseek-v4-flash
  if (parts.length >= 2) {
    const provider = parts[0]!;
    const model = parts.slice(1).join(" ");
    if (provider !== "deepseek" && provider !== "cliproxy") {
      opts.setNotice("usage: /model <deepseek|cliproxy> <model-id>");
      return;
    }
    const match = models.find((m) => m.provider === provider && m.model_id === model);
    if (!match) {
      opts.setNotice(`model not available: ${provider}/${model} · try /model`);
      return;
    }
    await opts.controller.setModel(match.provider, match.model_id);
    opts.setNotice(
      `model → ${match.provider}/${match.model_id} (ctx ${match.context_token_budget ?? "?"})`,
    );
    return;
  }

  // /model 0
  if (parts.length === 1 && /^\d+$/.test(parts[0]!)) {
    const idx = Number(parts[0]);
    const chosen = models[idx];
    if (!chosen) {
      opts.setNotice(`invalid index · use 0..${models.length - 1}`);
      return;
    }
    await opts.controller.setModel(chosen.provider, chosen.model_id);
    opts.setNotice(
      `model → ${chosen.provider}/${chosen.model_id} (ctx ${chosen.context_token_budget ?? "?"})`,
    );
    return;
  }

  opts.setNotice(
    "usage: /model | /model <n> | /model <provider> <model-id>",
  );
}

/** Re-read credentials from disk (after external edit). */
export function loadCredsFromDisk(): LocalCredentials {
  return readCredentialsFile(credentialsPath());
}
