import assert from "node:assert/strict";
import { chmod, mkdtemp, mkdir, readFile, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, it } from "node:test";

import {
  configureDevelopmentServer,
  formatServerCommand,
} from "../src/dev-config.js";
import { resolveServerCommand } from "../src/service-lifecycle.js";


describe("development service configuration", () => {
  it("persists an absolute project without replacing unrelated settings", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-dev-config-"));
    const configDir = join(root, "config", "typed-code");
    const project = join(root, "source");
    await mkdir(configDir, { recursive: true });
    await mkdir(project);
    await writeFile(join(project, "pyproject.toml"), "[project]\nname='fixture'\n");
    await writeFile(join(configDir, "config.toml"), "[listen]\nport = 9191\n");
    const env: NodeJS.ProcessEnv = {
      HOME: root,
      XDG_CONFIG_HOME: join(root, "config"),
      XDG_DATA_HOME: join(root, "data"),
    };
    try {
      const result = configureDevelopmentServer({ project, env });
      const canonicalProject = await realpath(project);
      assert.equal(result.command.kind, "development-project");
      assert.match(formatServerCommand(result.command), /uv run --project/);

      const body = await readFile(result.configPath, "utf8");
      assert.match(body, /\[listen\]\nport = 9191/);
      assert.match(body, /\[development\]/);
      assert.match(body, new RegExp(canonicalProject.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));

      const resolved = resolveServerCommand({ env, expectedRelease: "0.1.0" });
      assert.equal(resolved.args[2], canonicalProject);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  it("replaces a project configuration with an executable", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-dev-config-"));
    const project = join(root, "source");
    const executable = join(root, "typed-code-server");
    await mkdir(project);
    await writeFile(join(project, "pyproject.toml"), "[project]\nname='fixture'\n");
    await writeFile(executable, "#!/bin/sh\nexit 0\n");
    await chmod(executable, 0o755);
    const env: NodeJS.ProcessEnv = {
      HOME: root,
      XDG_CONFIG_HOME: join(root, "config"),
      XDG_DATA_HOME: join(root, "data"),
    };
    try {
      configureDevelopmentServer({ project, env });
      const result = configureDevelopmentServer({ executable, env });
      const body = await readFile(result.configPath, "utf8");
      assert.match(body, /executable = /);
      assert.doesNotMatch(body, /project = /);
      assert.equal(resolveServerCommand({ env }).command, await realpath(executable));
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
});
