/**
 * Ensure a local loopback typed-code serve is available.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { PROTOCOL_VERSION } from "@typed-code/sdk";

export interface ServiceHandle {
  baseUrl: string;
  token: string;
  /** True when this process spawned the child and should stop it on exit. */
  owned: boolean;
  child: ChildProcess | null;
}

export async function probeService(
  baseUrl: string,
  token: string,
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
): Promise<"ok" | "unreachable" | "protocol_mismatch" | "unauthorized"> {
  try {
    const healthRes = await fetchImpl(`${baseUrl}/v1/health`, {
      signal: AbortSignal.timeout(2000),
    });
    if (!healthRes.ok) {
      return "unreachable";
    }
    const health = (await healthRes.json()) as { protocol_version?: number };
    if (health.protocol_version !== PROTOCOL_VERSION) {
      return "protocol_mismatch";
    }
    const modelsRes = await fetchImpl(`${baseUrl}/v1/models`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(2000),
    });
    if (modelsRes.status === 401 || modelsRes.status === 403) {
      return "unauthorized";
    }
    if (!modelsRes.ok) {
      return "unreachable";
    }
    return "ok";
  } catch {
    return "unreachable";
  }
}

export async function ensureLocalService(opts: {
  baseUrl: string;
  token: string;
  fetchImpl?: typeof fetch;
  spawnServe?: () => ChildProcess;
  waitMs?: number;
}): Promise<ServiceHandle> {
  const fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  const status = await probeService(opts.baseUrl, opts.token, fetchImpl);
  if (status === "ok") {
    return {
      baseUrl: opts.baseUrl,
      token: opts.token,
      owned: false,
      child: null,
    };
  }
  if (status === "protocol_mismatch") {
    throw new Error(
      `incompatible service at ${opts.baseUrl} (protocol mismatch); stop it or use another port`,
    );
  }
  if (status === "unauthorized") {
    throw new Error(
      `service at ${opts.baseUrl} rejected the server token; check credentials.toml server_token`,
    );
  }

  const url = new URL(opts.baseUrl);
  const host = url.hostname || "127.0.0.1";
  const port = url.port || "8741";
  const child =
    opts.spawnServe?.() ??
    spawn("uv", ["run", "typed-code", "serve", "--host", host, "--port", port], {
      env: { ...process.env, TYPED_CODE_SERVER_TOKEN: opts.token },
      stdio: ["ignore", "pipe", "pipe"],
      detached: false,
    });

  const deadline = Date.now() + (opts.waitMs ?? 20_000);
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(
        `typed-code serve exited early with code ${child.exitCode ?? "unknown"}`,
      );
    }
    const s = await probeService(opts.baseUrl, opts.token, fetchImpl);
    if (s === "ok") {
      return { baseUrl: opts.baseUrl, token: opts.token, owned: true, child };
    }
    await sleep(200);
  }
  stopOwnedService({ baseUrl: opts.baseUrl, token: opts.token, owned: true, child });
  throw new Error(`timed out waiting for typed-code serve at ${opts.baseUrl}`);
}

export function stopOwnedService(handle: ServiceHandle): void {
  if (!handle.owned || !handle.child) {
    return;
  }
  const child = handle.child;
  if (child.exitCode !== null) {
    return;
  }
  try {
    child.kill("SIGTERM");
  } catch {
    // ignore
  }
  const killer = setTimeout(() => {
    try {
      if (child.exitCode === null) {
        child.kill("SIGKILL");
      }
    } catch {
      // ignore
    }
  }, 2000);
  killer.unref?.();
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
