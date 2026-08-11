/**
 * XDG credentials / config helpers for single-entry local use.
 * CLI may write secrets for setup; the server process loads them for providers.
 */

import { randomBytes } from "node:crypto";
import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

import type { ProviderName, ReasoningLevel } from "@typed-code/sdk";

export interface LocalCredentials {
  server_token?: string;
  deepseek_api_key?: string;
  cliproxy_api_key?: string;
}

export interface ModelPreference {
  provider: ProviderName;
  model: string;
  reasoning_level?: ReasoningLevel;
}

export function configDir(env: NodeJS.ProcessEnv = process.env): string {
  const xdg = env.XDG_CONFIG_HOME?.trim();
  if (xdg) {
    return join(xdg, "typed-code");
  }
  return join(homedir(), ".config", "typed-code");
}

export function credentialsPath(env: NodeJS.ProcessEnv = process.env): string {
  return join(configDir(env), "credentials.toml");
}

export function modelPreferencePath(env: NodeJS.ProcessEnv = process.env): string {
  return join(configDir(env), "preferences.toml");
}

export function ensureConfigDir(dir: string): void {
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true, mode: 0o700 });
  }
  try {
    chmodSync(dir, 0o700);
  } catch {
    // best effort on platforms that ignore mode
  }
}

/** Minimal TOML read for flat string keys we own. */
export function parseSimpleToml(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || line.startsWith("[")) {
      continue;
    }
    const eq = line.indexOf("=");
    if (eq <= 0) {
      continue;
    }
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    if (key) {
      out[key] = value;
    }
  }
  return out;
}

export function formatCredentialsToml(creds: LocalCredentials): string {
  const lines = [
    "# typed-code credentials — mode 0600; do not commit",
  ];
  if (creds.server_token) {
    lines.push(`server_token = ${tomlString(creds.server_token)}`);
  }
  if (creds.deepseek_api_key) {
    lines.push(`deepseek_api_key = ${tomlString(creds.deepseek_api_key)}`);
  }
  if (creds.cliproxy_api_key) {
    lines.push(`cliproxy_api_key = ${tomlString(creds.cliproxy_api_key)}`);
  }
  lines.push("");
  return lines.join("\n");
}

function tomlString(value: string): string {
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

export function readCredentialsFile(path: string): LocalCredentials {
  if (!existsSync(path)) {
    return {};
  }
  const raw = readFileSync(path, "utf8");
  const map = parseSimpleToml(raw);
  const out: LocalCredentials = {};
  if (map.server_token) out.server_token = map.server_token;
  if (map.deepseek_api_key) out.deepseek_api_key = map.deepseek_api_key;
  if (map.cliproxy_api_key) out.cliproxy_api_key = map.cliproxy_api_key;
  return out;
}

export function writeCredentialsFile(path: string, creds: LocalCredentials): void {
  writeFileSync(path, formatCredentialsToml(creds), { mode: 0o600 });
  try {
    chmodSync(path, 0o600);
  } catch {
    // best effort
  }
}

export function readModelPreference(path: string): ModelPreference | null {
  if (!existsSync(path)) return null;
  const map = parseSimpleToml(readFileSync(path, "utf8"));
  const provider = map.provider;
  const model = map.model?.trim();
  if ((provider !== "deepseek" && provider !== "cliproxy") || !model) {
    return null;
  }
  const rawReasoning = map.reasoning_level;
  const reasoning_level =
    rawReasoning === "none" ||
    rawReasoning === "low" ||
    rawReasoning === "medium" ||
    rawReasoning === "high" ||
    rawReasoning === "xhigh" ||
    rawReasoning === "max"
      ? rawReasoning
      : undefined;
  return reasoning_level
    ? { provider, model, reasoning_level }
    : { provider, model };
}

export function writeModelPreference(path: string, preference: ModelPreference): void {
  const lines = [
    "# typed-code local preferences",
    `provider = ${tomlString(preference.provider)}`,
    `model = ${tomlString(preference.model)}`,
  ];
  if (preference.reasoning_level) {
    lines.push(`reasoning_level = ${tomlString(preference.reasoning_level)}`);
  }
  lines.push("");
  const body = lines.join("\n");
  writeFileSync(path, body, { mode: 0o600 });
  try {
    chmodSync(path, 0o600);
  } catch {
    // best effort on platforms that ignore mode
  }
}

export function hasAnyProviderKey(creds: LocalCredentials): boolean {
  return Boolean(creds.deepseek_api_key?.trim() || creds.cliproxy_api_key?.trim());
}

export function generateServerToken(): string {
  return randomBytes(16).toString("hex");
}

/**
 * Ensure credentials file exists with server_token.
 * Does not require provider keys.
 */
export function ensureLocalCredentials(env: NodeJS.ProcessEnv = process.env): {
  path: string;
  creds: LocalCredentials;
} {
  const dir = configDir(env);
  ensureConfigDir(dir);
  const path = credentialsPath(env);
  let creds = readCredentialsFile(path);

  // Env fallbacks when file field absent (file-first: only fill missing)
  if (!creds.server_token && env.TYPED_CODE_SERVER_TOKEN?.trim()) {
    creds = { ...creds, server_token: env.TYPED_CODE_SERVER_TOKEN.trim() };
  }
  if (!creds.deepseek_api_key && env.DEEPSEEK_API_KEY?.trim()) {
    creds = { ...creds, deepseek_api_key: env.DEEPSEEK_API_KEY.trim() };
  }
  if (!creds.cliproxy_api_key && env.CLIPROXY_API_KEY?.trim()) {
    creds = { ...creds, cliproxy_api_key: env.CLIPROXY_API_KEY.trim() };
  }

  if (!creds.server_token) {
    creds = { ...creds, server_token: generateServerToken() };
  }

  writeCredentialsFile(path, creds);
  return { path, creds };
}

export function mergeProviderKeys(
  existing: LocalCredentials,
  patch: { deepseek_api_key?: string; cliproxy_api_key?: string },
): LocalCredentials {
  const next = { ...existing };
  if (patch.deepseek_api_key?.trim()) {
    next.deepseek_api_key = patch.deepseek_api_key.trim();
  }
  if (patch.cliproxy_api_key?.trim()) {
    next.cliproxy_api_key = patch.cliproxy_api_key.trim();
  }
  return next;
}
