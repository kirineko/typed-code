/** Non-TUI management commands for the persistent user-scoped service. */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import type { HealthResponse } from "@typed-code/sdk";

import {
  credentialsPath,
  ensureLocalCredentials,
  readCredentialsFile,
} from "./local-config.js";
import {
  readServiceDescriptor,
  resolveServiceDataDir,
  resolveUserService,
  serviceDescriptorPath,
  type ServiceDescriptor,
  type ServiceHandle,
} from "./service-lifecycle.js";

export interface ServerStatus {
  running: boolean;
  descriptor: ServiceDescriptor | null;
  health: HealthResponse | null;
}

export async function inspectUserService(
  env: NodeJS.ProcessEnv = process.env,
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<ServerStatus> {
  const descriptor = readServiceDescriptor(serviceDescriptorPath(env));
  if (!descriptor) return { running: false, descriptor: null, health: null };
  const token = requireServerToken(env);
  let handle: ServiceHandle;
  try {
    handle = await resolveUserService({
      token,
      allowStart: false,
      env,
      fetchImpl,
    });
  } catch (error) {
    if (error instanceof Error && error.message.includes("service is not running")) {
      return { running: false, descriptor, health: null };
    }
    throw error;
  }
  const response = await fetchImpl(`${handle.baseUrl}/v1/health`, {
    signal: AbortSignal.timeout(2_000),
  });
  if (!response.ok) throw new Error(`service health failed: HTTP ${response.status}`);
  return {
    running: true,
    descriptor: handle.descriptor,
    health: (await response.json()) as HealthResponse,
  };
}

export async function startUserService(
  env: NodeJS.ProcessEnv = process.env,
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<ServiceHandle> {
  const { creds } = ensureLocalCredentials(env);
  if (!creds.server_token) throw new Error("server token is unavailable");
  return resolveUserService({ token: creds.server_token, env, fetchImpl });
}

export async function stopUserService(opts: {
  force: boolean;
  env?: NodeJS.ProcessEnv;
  fetchImpl?: typeof fetch;
  waitMs?: number;
}): Promise<boolean> {
  const env = opts.env ?? process.env;
  const fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  if (!readServiceDescriptor(serviceDescriptorPath(env))) return false;
  const token = requireServerToken(env);
  const handle = await resolveUserService({
    token,
    allowStart: false,
    env,
    fetchImpl,
  });
  const response = await fetchImpl(`${handle.baseUrl}/v1/service/stop`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ force: opts.force }),
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) {
    throw new Error(await responseError(response));
  }
  const deadline = Date.now() + (opts.waitMs ?? 10_000);
  while (Date.now() < deadline) {
    if (!readServiceDescriptor(serviceDescriptorPath(env))) return true;
    await sleep(100);
  }
  throw new Error("timed out waiting for typed-code service to stop");
}

export async function restartUserService(opts: {
  force: boolean;
  env?: NodeJS.ProcessEnv;
  fetchImpl?: typeof fetch;
}): Promise<ServiceHandle> {
  const env = opts.env ?? process.env;
  const fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  await stopUserService({ force: opts.force, env, fetchImpl });
  return startUserService(env, fetchImpl);
}

export function readUserServiceLogs(opts: {
  lines: number;
  env?: NodeJS.ProcessEnv;
}): string {
  const env = opts.env ?? process.env;
  const logPath = join(resolveServiceDataDir(env), "runtime", "server.log");
  if (!existsSync(logPath)) return "";
  const credentials = readCredentialsFile(credentialsPath(env));
  let text = readFileSync(logPath, "utf8");
  for (const secret of Object.values(credentials)) {
    if (secret) text = text.replaceAll(secret, "[REDACTED]");
  }
  return text.split(/\r?\n/).slice(-opts.lines - 1).join("\n");
}

export async function runServerCommand(argv: string[]): Promise<number> {
  const { command, force, lines } = parseServerArgs(argv);
  switch (command) {
    case "status": {
      const status = await inspectUserService();
      console.log(formatServerStatus(status));
      return status.running ? 0 : 3;
    }
    case "start": {
      const handle = await startUserService();
      console.log(
        `running pid=${handle.descriptor?.pid ?? "unknown"} url=${handle.baseUrl} source=${handle.source}`,
      );
      return 0;
    }
    case "stop": {
      const stopped = await stopUserService({ force });
      console.log(stopped ? "stopped" : "already stopped");
      return 0;
    }
    case "restart": {
      const handle = await restartUserService({ force });
      console.log(`restarted pid=${handle.descriptor?.pid ?? "unknown"} url=${handle.baseUrl}`);
      return 0;
    }
    case "logs": {
      const logs = readUserServiceLogs({ lines });
      if (logs) process.stdout.write(logs.endsWith("\n") ? logs : `${logs}\n`);
      return 0;
    }
  }
}

export function serverHelpText(): string {
  return `Usage:
  typed-code server status
  typed-code server start
  typed-code server stop [--force]
  typed-code server restart [--force]
  typed-code server logs [--lines <count>]

Stop and restart refuse to interrupt active runs unless --force is explicit.`;
}

export function formatServerStatus(status: ServerStatus): string {
  if (!status.running || !status.health?.service) return "stopped";
  const service = status.health.service;
  const work = service.active_work;
  return [
    `running pid=${service.pid}`,
    `url=${service.base_url ?? status.descriptor?.base_url ?? "unknown"}`,
    `version=${service.service_version}`,
    `active_runs=${work.active_runs}`,
    `pending_approvals=${work.pending_approvals}`,
    `event_streams=${work.connected_event_streams}`,
  ].join(" ");
}

function parseServerArgs(argv: string[]): {
  command: "status" | "start" | "stop" | "restart" | "logs";
  force: boolean;
  lines: number;
} {
  const command = argv[0];
  if (command === "--help" || command === "-h" || !command) {
    throw new Error(serverHelpText());
  }
  if (!["status", "start", "stop", "restart", "logs"].includes(command)) {
    throw new Error(`unknown server command: ${command}\n${serverHelpText()}`);
  }
  let force = false;
  let lines = 100;
  for (let index = 1; index < argv.length; index++) {
    const arg = argv[index];
    if (arg === "--force" && (command === "stop" || command === "restart")) {
      force = true;
      continue;
    }
    if (arg === "--lines" && command === "logs") {
      const raw = argv[++index];
      lines = Number(raw);
      if (!Number.isInteger(lines) || lines < 1 || lines > 10_000) {
        throw new Error("--lines must be an integer between 1 and 10000");
      }
      continue;
    }
    throw new Error(`unexpected server argument: ${String(arg)}\n${serverHelpText()}`);
  }
  return {
    command: command as "status" | "start" | "stop" | "restart" | "logs",
    force,
    lines,
  };
}

function requireServerToken(env: NodeJS.ProcessEnv): string {
  const token =
    env.TYPED_CODE_SERVER_TOKEN?.trim() ||
    readCredentialsFile(credentialsPath(env)).server_token?.trim();
  if (!token) throw new Error("server token is missing from credentials.toml");
  return token;
}

async function responseError(response: Response): Promise<string> {
  try {
    const value = (await response.json()) as {
      error?: { message?: unknown };
    };
    if (typeof value.error?.message === "string") return value.error.message;
  } catch {
    // Fall through to the bounded HTTP diagnostic.
  }
  return `service request failed: HTTP ${response.status}`;
}

function sleep(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}
