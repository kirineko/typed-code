import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import {
  appendFile,
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { promisify } from "node:util";
import { after, describe, it } from "node:test";

const execute = promisify(execFile);
const roots: string[] = [];
const tsxImport = import.meta.resolve("tsx");
const projectRoot = resolve(dirname(new URL(import.meta.url).pathname), "../../..");
const cliEntry = join(projectRoot, "packages", "cli", "src", "bin.ts");

after(async () => {
  await Promise.all(roots.map((root) => rm(root, { recursive: true, force: true })));
});

describe("server management process lifecycle", () => {
  it("starts idempotently, reports status, redacts logs, restarts, and stops", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-server-process-"));
    roots.push(root);
    const port = await freePort();
    const configHome = join(root, "config");
    const configDir = join(configHome, "typed-code");
    const dataDir = join(root, "data");
    await mkdir(configDir, { recursive: true, mode: 0o700 });
    await writeFile(
      join(configDir, "config.toml"),
      [
        "[listen]",
        'host = "127.0.0.1"',
        `port = ${port}`,
        "",
        "[data]",
        `dir = ${JSON.stringify(dataDir)}`,
        "",
        "[development]",
        `project = ${JSON.stringify(projectRoot)}`,
        "",
      ].join("\n"),
      { mode: 0o600 },
    );
    const credentialPath = join(configDir, "credentials.toml");
    await writeFile(
      credentialPath,
      [
        'server_token = "process-server-secret"',
        'cliproxy_api_key = "process-provider-secret"',
        "",
      ].join("\n"),
      { mode: 0o600 },
    );
    await chmod(credentialPath, 0o600);
    const env = {
      ...process.env,
      XDG_CONFIG_HOME: configHome,
      XDG_DATA_HOME: join(root, "data-home"),
    };
    const run = async (...args: string[]) =>
      execute(process.execPath, ["--import", tsxImport, cliEntry, "server", ...args], {
        cwd: root,
        env,
        timeout: 30_000,
      });

    try {
      const first = await run("start");
      assert.match(first.stdout, /source=started/);
      const firstDescriptor = JSON.parse(
        await readFile(join(dataDir, "runtime", "service.json"), "utf8"),
      ) as { pid: number };

      const second = await run("start");
      assert.match(second.stdout, /source=existing/);
      const status = await run("status");
      assert.match(status.stdout, new RegExp(`running pid=${firstDescriptor.pid}`));
      assert.match(status.stdout, /active_runs=0/);

      await appendFile(
        join(dataDir, "runtime", "server.log"),
        "process-server-secret process-provider-secret visible-marker\n",
      );
      const logs = await run("logs", "--lines", "20");
      assert.doesNotMatch(logs.stdout, /process-(?:server|provider)-secret/);
      assert.match(logs.stdout, /\[REDACTED\] \[REDACTED\] visible-marker/);

      const restarted = await run("restart");
      const secondDescriptor = JSON.parse(
        await readFile(join(dataDir, "runtime", "service.json"), "utf8"),
      ) as { pid: number };
      assert.match(restarted.stdout, /restarted pid=/);
      assert.notEqual(secondDescriptor.pid, firstDescriptor.pid);

      const stopped = await run("stop");
      assert.match(stopped.stdout, /^stopped/m);
      const stoppedAgain = await run("stop");
      assert.match(stoppedAgain.stdout, /already stopped/);
    } finally {
      try {
        await run("stop", "--force");
      } catch {
        // The successful path already stopped it.
      }
    }
  });
});

async function freePort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolveReady, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveReady);
  });
  const address = server.address();
  assert(address && typeof address === "object");
  const port = address.port;
  await new Promise<void>((resolveClosed, reject) => {
    server.close((error) => (error ? reject(error) : resolveClosed()));
  });
  return port;
}
