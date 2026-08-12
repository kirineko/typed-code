import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, describe, it } from "node:test";

import { readUserServiceLogs } from "../src/server-command.ts";

const roots: string[] = [];
after(async () => {
  await Promise.all(roots.map((root) => rm(root, { recursive: true, force: true })));
});

describe("server log access", () => {
  it("returns a bounded tail and redacts every configured credential", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-server-logs-"));
    roots.push(root);
    const configHome = join(root, "config");
    const dataDir = join(root, "data");
    const runtimeDir = join(dataDir, "runtime");
    const typedConfig = join(configHome, "typed-code");
    await mkdir(runtimeDir, { recursive: true, mode: 0o700 });
    await mkdir(typedConfig, { recursive: true, mode: 0o700 });
    await writeFile(
      join(typedConfig, "credentials.toml"),
      [
        'server_token = "server-secret-value"',
        'deepseek_api_key = "deepseek-secret-value"',
        'cliproxy_api_key = "cliproxy-secret-value"',
        "",
      ].join("\n"),
      { mode: 0o600 },
    );
    await writeFile(
      join(runtimeDir, "server.log"),
      [
        "discarded old line",
        "auth server-secret-value",
        "deepseek deepseek-secret-value",
        "cliproxy cliproxy-secret-value",
        "visible tail",
        "",
      ].join("\n"),
      { mode: 0o600 },
    );

    const env = {
      HOME: root,
      XDG_CONFIG_HOME: configHome,
      TYPED_CODE_DATA_DIR: dataDir,
    };
    const logs = readUserServiceLogs({ lines: 4, env });

    assert.doesNotMatch(logs, /discarded old line/);
    assert.doesNotMatch(logs, /secret-value/);
    assert.equal(logs.match(/\[REDACTED\]/g)?.length, 3);
    assert.match(logs, /visible tail/);
    assert.equal((await stat(runtimeDir)).mode & 0o777, 0o700);
    assert.equal((await stat(join(runtimeDir, "server.log"))).mode & 0o777, 0o600);
  });
});
