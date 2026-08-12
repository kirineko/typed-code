/**
 * Resolve or atomically start the persistent user-scoped typed-code service.
 */

import { randomUUID } from "node:crypto";
import { spawn, type ChildProcess } from "node:child_process";
import { createRequire } from "node:module";
import {
  accessSync,
  chmodSync,
  closeSync,
  constants,
  existsSync,
  mkdirSync,
  openSync,
  readFileSync,
  realpathSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";

import { PROTOCOL_VERSION, type HealthResponse } from "@typed-code/sdk";

import { configDir } from "./local-config.js";

const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 8741;
const STARTUP_CLAIM_STALE_MS = 30_000;

export type ServiceProbeStatus =
  | "ok"
  | "unreachable"
  | "protocol_mismatch"
  | "release_mismatch"
  | "unauthorized"
  | "legacy_service";

export interface ServiceDescriptor {
  pid: number;
  instance_id: string;
  base_url: string;
  service_version: string;
  protocol_version: number;
  data_dir: string;
  started_at: string;
}

export interface ServiceHandle {
  baseUrl: string;
  token: string;
  source: "external" | "existing" | "started";
  descriptor: ServiceDescriptor | null;
}

export interface ServerCommand {
  command: string;
  args: string[];
  kind: "executable" | "development-project" | "companion";
}

export interface ServiceLaunch {
  command: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
  logPath: string;
}

export interface ServiceResolverOptions {
  token: string;
  baseUrl?: string | undefined;
  external?: boolean | undefined;
  allowStart?: boolean | undefined;
  env?: NodeJS.ProcessEnv | undefined;
  fetchImpl?: typeof fetch | undefined;
  spawnDetached?: ((launch: ServiceLaunch) => ChildProcess) | undefined;
  waitMs?: number | undefined;
  expectedRelease?: string | undefined;
  platform?: NodeJS.Platform | undefined;
  arch?: string | undefined;
}

interface ProbeResult {
  status: ServiceProbeStatus;
  health: HealthResponse | null;
}

interface StartupClaim {
  path: string;
  nonce: string;
}

interface ServiceSettings {
  dataDir: string;
  baseUrl: string;
  developmentExecutable: string | null;
  developmentProject: string | null;
}

export async function probeService(
  baseUrl: string,
  token: string,
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis),
  expectedRelease?: string,
): Promise<ServiceProbeStatus> {
  return (await probeServiceDetails(baseUrl, token, fetchImpl, expectedRelease)).status;
}

export async function resolveUserService(
  opts: ServiceResolverOptions,
): Promise<ServiceHandle> {
  const env = opts.env ?? process.env;
  const fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  const expectedRelease = opts.expectedRelease ?? readCliVersion();
  const settings = resolveServiceSettings(env);
  const external = opts.external ?? false;
  const allowStart = opts.allowStart ?? !external;
  const requestedBaseUrl = normalizeBaseUrl(opts.baseUrl ?? settings.baseUrl);

  if (external) {
    const result = await probeServiceDetails(
      requestedBaseUrl,
      opts.token,
      fetchImpl,
      expectedRelease,
    );
    requireCompatible(result, requestedBaseUrl);
    return {
      baseUrl: requestedBaseUrl,
      token: opts.token,
      source: "external",
      descriptor: null,
    };
  }

  const runtimeDir = join(settings.dataDir, "runtime");
  const descriptorPath = join(runtimeDir, "service.json");
  const startupClaimPath = join(runtimeDir, "startup.lock");
  ensurePrivateDirectory(settings.dataDir);
  ensurePrivateDirectory(runtimeDir);

  const existing = await inspectDescriptor(
    descriptorPath,
    settings.dataDir,
    opts.token,
    fetchImpl,
    expectedRelease,
  );
  if (existing) {
    return { ...existing, source: "existing" };
  }

  const direct = await probeServiceDetails(
    requestedBaseUrl,
    opts.token,
    fetchImpl,
    expectedRelease,
  );
  if (direct.status !== "unreachable") {
    if (direct.status === "ok" && direct.health) {
      const service = direct.health.service;
      if (canonicalPath(service.data_dir, env) === settings.dataDir) {
        // The owner has bound its socket and is about to publish service.json.
      } else {
        throw new Error(
          `service endpoint ${requestedBaseUrl} belongs to data directory ${service.data_dir}, not ${settings.dataDir}`,
        );
      }
    } else {
      requireCompatible(direct, requestedBaseUrl);
    }
  }

  if (!allowStart) {
    throw new Error(`typed-code service is not running at ${requestedBaseUrl}`);
  }

  const deadline = Date.now() + (opts.waitMs ?? 30_000);
  let claim: StartupClaim | null = null;
  let spawned = false;
  let spawnFailure: string | null = null;
  try {
    while (Date.now() < deadline) {
      const available = await inspectDescriptor(
        descriptorPath,
        settings.dataDir,
        opts.token,
        fetchImpl,
        expectedRelease,
      );
      if (available) {
        return { ...available, source: spawned ? "started" : "existing" };
      }

      if (!claim && !spawned) {
        claim = tryAcquireStartupClaim(startupClaimPath);
        if (claim) {
          const command = resolveServerCommand({
            env,
            settings,
            expectedRelease,
            platform: opts.platform ?? process.platform,
            arch: opts.arch ?? process.arch,
            baseUrl: requestedBaseUrl,
          });
          try {
            const child = (opts.spawnDetached ?? spawnDetachedService)({
              command: command.command,
              args: command.args,
              cwd: settings.dataDir,
              env: {
                ...env,
                TYPED_CODE_DATA_DIR: settings.dataDir,
                TYPED_CODE_SERVER_TOKEN: opts.token,
              },
              logPath: join(runtimeDir, "server.log"),
            });
            spawned = true;
            child.once("error", (error) => {
              spawnFailure = error.message;
            });
          } catch (error) {
            spawnFailure = error instanceof Error ? error.message : String(error);
            throw new Error(`failed to start typed-code service: ${spawnFailure}`);
          }
        }
      }

      await sleep(100);
    }
  } finally {
    if (claim) {
      releaseStartupClaim(claim);
    }
  }

  if (spawnFailure) {
    throw new Error(`typed-code service failed to start: ${spawnFailure}`);
  }
  throw new Error(
    `timed out waiting for authenticated typed-code service in ${settings.dataDir}`,
  );
}

export function resolveServerCommand(opts: {
  env?: NodeJS.ProcessEnv;
  settings?: ServiceSettings;
  expectedRelease?: string;
  platform?: NodeJS.Platform;
  arch?: string;
  baseUrl?: string;
} = {}): ServerCommand {
  const env = opts.env ?? process.env;
  const settings = opts.settings ?? resolveServiceSettings(env);
  const expectedRelease = opts.expectedRelease ?? readCliVersion();
  const baseUrl = normalizeBaseUrl(opts.baseUrl ?? settings.baseUrl);
  const url = new URL(baseUrl);
  const serveArgs = ["serve", "--host", url.hostname, "--port", url.port || "80"];

  const executable =
    env.TYPED_CODE_SERVER_EXECUTABLE?.trim() || settings.developmentExecutable;
  if (executable) {
    const absolute = requireAbsoluteExistingPath(executable, "development server executable", env);
    if (!statSync(absolute).isFile()) {
      throw new Error(`development server executable is not a file: ${absolute}`);
    }
    requireExecutablePermission(absolute, "development server executable");
    return { command: absolute, args: serveArgs, kind: "executable" };
  }

  const project = env.TYPED_CODE_SERVER_PROJECT?.trim() || settings.developmentProject;
  if (project) {
    const absolute = requireAbsoluteExistingPath(project, "development source project", env);
    if (!statSync(absolute).isDirectory() || !existsSync(join(absolute, "pyproject.toml"))) {
      throw new Error(
        `development source project must contain pyproject.toml: ${absolute}`,
      );
    }
    return {
      command: env.TYPED_CODE_UV_EXECUTABLE?.trim() || "uv",
      args: ["run", "--project", absolute, "typed-code", ...serveArgs],
      kind: "development-project",
    };
  }

  const platform = opts.platform ?? process.platform;
  const arch = opts.arch ?? process.arch;
  const companion = companionPackage(platform, arch);
  if (!companion) {
    throw new Error(
      `unsupported typed-code service target ${platform}/${arch}; supported target: darwin/arm64. Configure an absolute TYPED_CODE_SERVER_EXECUTABLE or TYPED_CODE_SERVER_PROJECT for development`,
    );
  }

  const require = createRequire(import.meta.url);
  let packagePath: string;
  try {
    packagePath = require.resolve(`${companion}/package.json`);
  } catch {
    throw new Error(
      `missing ${companion} service companion for ${platform}/${arch}; reinstall @typed-code/cli or configure an explicit development server`,
    );
  }
  const packageJson = parseJsonObject(readFileSync(packagePath, "utf8"));
  if (packageJson.version !== expectedRelease) {
    throw new Error(
      `service companion release mismatch: cli=${expectedRelease} companion=${String(packageJson.version ?? "unknown")}`,
    );
  }
  const binary = join(dirname(packagePath), "bin", "typed-code-server");
  if (!existsSync(binary) || !statSync(binary).isFile()) {
    throw new Error(`service companion executable is missing: ${binary}`);
  }
  requireExecutablePermission(binary, "service companion executable");
  return { command: binary, args: serveArgs, kind: "companion" };
}

export function resolveServiceDataDir(env: NodeJS.ProcessEnv = process.env): string {
  return resolveServiceSettings(env).dataDir;
}

export function serviceDescriptorPath(env: NodeJS.ProcessEnv = process.env): string {
  return join(resolveServiceDataDir(env), "runtime", "service.json");
}

export function readServiceDescriptor(path: string): ServiceDescriptor | null {
  try {
    const value = parseJsonObject(readFileSync(path, "utf8"));
    if (
      typeof value.pid !== "number" ||
      !Number.isInteger(value.pid) ||
      value.pid < 1 ||
      typeof value.instance_id !== "string" ||
      !value.instance_id ||
      typeof value.base_url !== "string" ||
      typeof value.service_version !== "string" ||
      typeof value.protocol_version !== "number" ||
      typeof value.data_dir !== "string" ||
      typeof value.started_at !== "string"
    ) {
      return null;
    }
    return value as unknown as ServiceDescriptor;
  } catch {
    return null;
  }
}

async function inspectDescriptor(
  descriptorPath: string,
  dataDir: string,
  token: string,
  fetchImpl: typeof fetch,
  expectedRelease: string,
): Promise<Omit<ServiceHandle, "source"> | null> {
  const descriptor = readServiceDescriptor(descriptorPath);
  if (!descriptor) {
    return null;
  }
  if (canonicalPath(descriptor.data_dir, process.env) !== dataDir) {
    return null;
  }
  const baseUrl = normalizeBaseUrl(descriptor.base_url);
  const result = await probeServiceDetails(baseUrl, token, fetchImpl, expectedRelease);
  if (result.status === "unreachable") {
    return null;
  }
  requireCompatible(result, baseUrl);
  const service = result.health?.service;
  if (
    !service ||
    service.instance_id !== descriptor.instance_id ||
    service.pid !== descriptor.pid ||
    canonicalPath(service.data_dir, process.env) !== dataDir
  ) {
    throw new Error(
      `service identity mismatch between ${descriptorPath} and authenticated health`,
    );
  }
  return { baseUrl, token, descriptor };
}

async function probeServiceDetails(
  baseUrl: string,
  token: string,
  fetchImpl: typeof fetch,
  expectedRelease?: string,
): Promise<ProbeResult> {
  try {
    const healthRes = await fetchImpl(`${baseUrl}/v1/health`, {
      signal: AbortSignal.timeout(2000),
    });
    if (!healthRes.ok) {
      return { status: "unreachable", health: null };
    }
    const health = (await healthRes.json()) as Partial<HealthResponse>;
    if (health.protocol_version !== PROTOCOL_VERSION) {
      return { status: "protocol_mismatch", health: null };
    }
    if (expectedRelease) {
      if (!health.service || typeof health.service.service_version !== "string") {
        return { status: "legacy_service", health: null };
      }
      if (health.service.service_version !== expectedRelease) {
        return { status: "release_mismatch", health: null };
      }
    }
    const modelsRes = await fetchImpl(`${baseUrl}/v1/models`, {
      headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(2000),
    });
    if (modelsRes.status === 401 || modelsRes.status === 403) {
      return { status: "unauthorized", health: null };
    }
    if (!modelsRes.ok) {
      return { status: "unreachable", health: null };
    }
    return { status: "ok", health: health as HealthResponse };
  } catch {
    return { status: "unreachable", health: null };
  }
}

function requireCompatible(result: ProbeResult, baseUrl: string): void {
  switch (result.status) {
    case "ok":
      return;
    case "unreachable":
      throw new Error(`typed-code service is unreachable at ${baseUrl}`);
    case "protocol_mismatch":
      throw new Error(
        `incompatible service at ${baseUrl}: protocol does not match ${PROTOCOL_VERSION}`,
      );
    case "release_mismatch":
      throw new Error(`incompatible service release at ${baseUrl}; restart or reinstall`);
    case "unauthorized":
      throw new Error(
        `service at ${baseUrl} rejected the server token; check credentials.toml server_token`,
      );
    case "legacy_service":
      throw new Error(
        `legacy unmanaged typed-code service at ${baseUrl}; stop it before using the user-scoped launcher`,
      );
  }
}

function resolveServiceSettings(env: NodeJS.ProcessEnv): ServiceSettings {
  const configPath = join(configDir(env), "config.toml");
  const config = existsSync(configPath) ? readFileSync(configPath, "utf8") : "";
  const configuredDataDir = readTomlValue(config, "data", "dir");
  const dataDir = canonicalPath(
    configuredDataDir || env.TYPED_CODE_DATA_DIR?.trim() || defaultDataDir(env),
    env,
  );
  const host =
    readTomlValue(config, "listen", "host") ||
    env.TYPED_CODE_HOST?.trim() ||
    DEFAULT_HOST;
  const rawPort =
    readTomlValue(config, "listen", "port") ||
    env.TYPED_CODE_PORT?.trim() ||
    String(DEFAULT_PORT);
  const port = Number.parseInt(rawPort, 10);
  if (!Number.isInteger(port) || port < 1 || port > 65_535) {
    throw new Error(`invalid typed-code service port: ${rawPort}`);
  }
  const developmentExecutable =
    readTomlValue(config, "development", "executable") || null;
  const developmentProject = readTomlValue(config, "development", "project") || null;
  const hostForUrl = host.includes(":") && !host.startsWith("[") ? `[${host}]` : host;
  return {
    dataDir,
    baseUrl: `http://${hostForUrl}:${port}`,
    developmentExecutable,
    developmentProject,
  };
}

function readTomlValue(text: string, section: string, key: string): string | null {
  let activeSection = "";
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const sectionMatch = /^\[([^\]]+)\]$/.exec(line);
    if (sectionMatch) {
      activeSection = sectionMatch[1]?.trim() ?? "";
      continue;
    }
    if (activeSection !== section) continue;
    const equals = line.indexOf("=");
    if (equals < 1 || line.slice(0, equals).trim() !== key) continue;
    const value = line.slice(equals + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      return value.slice(1, -1);
    }
    return value.split("#", 1)[0]?.trim() || null;
  }
  return null;
}

function defaultDataDir(env: NodeJS.ProcessEnv): string {
  const xdg = env.XDG_DATA_HOME?.trim();
  return xdg ? join(xdg, "typed-code") : join(homeFor(env), ".local", "share", "typed-code");
}

function canonicalPath(path: string, env: NodeJS.ProcessEnv): string {
  const expanded = path.startsWith("~/") ? join(homeFor(env), path.slice(2)) : path;
  const absolute = resolve(expanded);
  let existing = absolute;
  const suffix: string[] = [];
  while (!existsSync(existing)) {
    const parent = dirname(existing);
    if (parent === existing) return absolute;
    suffix.unshift(basename(existing));
    existing = parent;
  }
  return join(realpathSync.native(existing), ...suffix);
}

function homeFor(env: NodeJS.ProcessEnv): string {
  return env.HOME?.trim() || homedir();
}

function normalizeBaseUrl(value: string): string {
  const normalized = value.replace(/\/+$/, "");
  const url = new URL(normalized);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`unsupported service URL protocol: ${url.protocol}`);
  }
  return normalized;
}

function requireAbsoluteExistingPath(
  value: string,
  label: string,
  env: NodeJS.ProcessEnv,
): string {
  const expanded = value.startsWith("~/") ? join(homeFor(env), value.slice(2)) : value;
  if (!isAbsolute(expanded)) {
    throw new Error(`${label} must be an absolute path: ${value}`);
  }
  const absolute = canonicalPath(expanded, env);
  if (!existsSync(absolute)) {
    throw new Error(`${label} does not exist: ${absolute}`);
  }
  return absolute;
}

function requireExecutablePermission(path: string, label: string): void {
  try {
    accessSync(path, constants.X_OK);
  } catch {
    throw new Error(`${label} is not executable: ${path}`);
  }
}

function ensurePrivateDirectory(path: string): void {
  mkdirSync(path, { recursive: true, mode: 0o700 });
  chmodSync(path, 0o700);
}

function tryAcquireStartupClaim(path: string): StartupClaim | null {
  const nonce = randomUUID();
  try {
    writeFileSync(
      path,
      JSON.stringify({ pid: process.pid, nonce, created_at: new Date().toISOString() }),
      { flag: "wx", mode: 0o600 },
    );
    return { path, nonce };
  } catch (error) {
    if (!isAlreadyExists(error)) throw error;
  }

  if (!startupClaimIsStale(path)) {
    return null;
  }
  try {
    unlinkSync(path);
  } catch {
    return null;
  }
  return tryAcquireStartupClaim(path);
}

function startupClaimIsStale(path: string): boolean {
  try {
    const info = statSync(path);
    const value = parseJsonObject(readFileSync(path, "utf8"));
    const pid = typeof value.pid === "number" ? value.pid : null;
    if (pid !== null && !processIsAlive(pid)) return true;
    return Date.now() - info.mtimeMs > STARTUP_CLAIM_STALE_MS;
  } catch {
    return true;
  }
}

function processIsAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}

function releaseStartupClaim(claim: StartupClaim): void {
  try {
    const value = parseJsonObject(readFileSync(claim.path, "utf8"));
    if (value.nonce === claim.nonce) unlinkSync(claim.path);
  } catch {
    // A replacement claim is never removed by a former contender.
  }
}

function spawnDetachedService(launch: ServiceLaunch): ChildProcess {
  const logFd = openSync(launch.logPath, "a", 0o600);
  try {
  chmodSync(launch.logPath, 0o600);
    const child = spawn(launch.command, launch.args, {
      cwd: launch.cwd,
      env: launch.env,
      stdio: ["ignore", logFd, logFd],
      detached: true,
    });
    child.unref();
    return child;
  } finally {
    closeSync(logFd);
  }
}

function companionPackage(platform: NodeJS.Platform, arch: string): string | null {
  if (platform === "darwin" && arch === "arm64") {
    return "@typed-code/server-darwin-arm64";
  }
  return null;
}

function readCliVersion(): string {
  const value = parseJsonObject(
    readFileSync(new URL("../package.json", import.meta.url), "utf8"),
  );
  if (typeof value.version !== "string" || !value.version) {
    throw new Error("@typed-code/cli package version is unavailable");
  }
  return value.version;
}

function parseJsonObject(text: string): Record<string, unknown> {
  const value: unknown = JSON.parse(text);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("expected a JSON object");
  }
  return value as Record<string, unknown>;
}

function isAlreadyExists(error: unknown): boolean {
  return (error as NodeJS.ErrnoException).code === "EEXIST";
}

function sleep(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}
