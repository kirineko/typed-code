/** One-time, cwd-independent development service configuration. */

import {
  chmodSync,
  existsSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";

import { configDir, ensureConfigDir } from "./local-config.js";
import { resolveServerCommand, type ServerCommand } from "./service-lifecycle.js";

export interface DevelopmentConfigurationResult {
  configPath: string;
  command: ServerCommand;
}

export function configureDevelopmentServer(opts: {
  project?: string | undefined;
  executable?: string | undefined;
  env?: NodeJS.ProcessEnv | undefined;
}): DevelopmentConfigurationResult {
  if (Boolean(opts.project) === Boolean(opts.executable)) {
    throw new Error("choose exactly one of --project or --executable");
  }
  const env = opts.env ?? process.env;
  const validationEnv: NodeJS.ProcessEnv = {
    ...env,
    TYPED_CODE_SERVER_PROJECT: opts.project,
    TYPED_CODE_SERVER_EXECUTABLE: opts.executable,
  };
  const command = resolveServerCommand({ env: validationEnv });
  const configPath = join(configDir(env), "config.toml");
  ensureConfigDir(dirname(configPath));
  const existing = existsSync(configPath) ? readFileSync(configPath, "utf8") : "";
  const configuredValue =
    command.kind === "development-project" ? command.args[2] : command.command;
  if (!configuredValue) {
    throw new Error("resolved development server path is unavailable");
  }
  const section =
    command.kind === "development-project"
      ? [`project = ${tomlString(configuredValue)}`]
      : [`executable = ${tomlString(configuredValue)}`];
  const updated = replaceTomlSection(existing, "development", section);
  atomicWrite(configPath, updated);
  return { configPath, command };
}

export function formatServerCommand(command: ServerCommand): string {
  return [command.command, ...command.args].map(shellQuote).join(" ");
}

function replaceTomlSection(text: string, section: string, body: string[]): string {
  const lines = text.replace(/\s+$/, "").split("\n");
  if (lines.length === 1 && lines[0] === "") lines.length = 0;
  const header = `[${section}]`;
  const start = lines.findIndex((line) => line.trim() === header);
  const replacement = [header, ...body];
  if (start < 0) {
    if (lines.length > 0) lines.push("");
    lines.push(...replacement);
  } else {
    let end = start + 1;
    while (end < lines.length && !/^\s*\[.+\]\s*$/.test(lines[end] ?? "")) {
      end += 1;
    }
    lines.splice(start, end - start, ...replacement, ...(end < lines.length ? [""] : []));
  }
  return `${lines.join("\n")}\n`;
}

function atomicWrite(path: string, content: string): void {
  const temporary = `${path}.${process.pid}.tmp`;
  try {
    writeFileSync(temporary, content, { mode: 0o600, flag: "wx" });
    chmodSync(temporary, 0o600);
    renameSync(temporary, path);
  } finally {
    try {
      unlinkSync(temporary);
    } catch {
      // rename already consumed the temporary path.
    }
  }
}

function tomlString(value: string): string {
  return `"${value.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

function shellQuote(value: string): string {
  if (/^[A-Za-z0-9_./:@%+=,-]+$/.test(value)) return value;
  return `'${value.replace(/'/g, `'"'"'`)}'`;
}
