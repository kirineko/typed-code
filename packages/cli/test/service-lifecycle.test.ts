import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { mkdirSync, writeFileSync } from "node:fs";
import { chmod, mkdtemp, mkdir, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { describe, it } from "node:test";
import type { ChildProcess } from "node:child_process";

import {
  resolveServerCommand,
  probeService,
  resolveServiceDataDir,
  resolveUserService,
  serviceDescriptorPath,
  type ServiceDescriptor,
} from "../src/service-lifecycle.js";

const RELEASE = "0.1.0";
const TOKEN = "test-token";

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function health(descriptor: ServiceDescriptor): object {
  return {
    status: "ok",
    protocol_version: 1,
    service: {
      service_version: descriptor.service_version,
      protocol_version: descriptor.protocol_version,
      instance_id: descriptor.instance_id,
      pid: descriptor.pid,
      started_at: descriptor.started_at,
      data_dir: descriptor.data_dir,
      base_url: descriptor.base_url,
      managed: true,
      active_work: {
        active_runs: 0,
        pending_approvals: 0,
        connected_event_streams: 0,
      },
    },
    providers: {},
    bash: { ready: true, executable: "/bin/bash" },
  };
}

function fakeServiceFetch(
  healthBody: object,
  modelsStatus = 200,
): typeof fetch {
  return async (input, init) => {
    const url = String(input);
    if (url.endsWith("/v1/health")) return jsonResponse(healthBody);
    if (url.endsWith("/v1/models")) {
      const authorization = new Headers(init?.headers).get("authorization");
      if (authorization !== `Bearer ${TOKEN}`) {
        return jsonResponse({ error: "unauthorized" }, 401);
      }
      return jsonResponse({ models: [] }, modelsStatus);
    }
    return jsonResponse({}, 404);
  };
}

async function withResolverEnvironment(
  run: (fixture: {
    env: NodeJS.ProcessEnv;
    dataDir: string;
    descriptorPath: string;
    cleanup: () => Promise<void>;
  }) => Promise<void>,
): Promise<void> {
  const root = await mkdtemp(join(tmpdir(), "typed-code-launcher-"));
  const project = join(root, "source");
  await mkdir(project, { recursive: true });
  await writeFile(join(project, "pyproject.toml"), "[project]\nname='fixture'\n");
  const env: NodeJS.ProcessEnv = {
    HOME: root,
    XDG_CONFIG_HOME: join(root, "config"),
    XDG_DATA_HOME: join(root, "data"),
    TYPED_CODE_SERVER_PROJECT: project,
  };
  const dataDir = resolveServiceDataDir(env);
  const descriptorPath = serviceDescriptorPath(env);
  try {
    await run({
      env,
      dataDir,
      descriptorPath,
      cleanup: () => rm(root, { recursive: true, force: true }),
    });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

describe("user-scoped service launcher", () => {
  it("coordinates concurrent cold starts with one detached spawn", async () => {
    await withResolverEnvironment(async ({ env, dataDir, descriptorPath }) => {
      let descriptor: ServiceDescriptor | null = null;
      let spawnCount = 0;
      const fetchImpl: typeof fetch = async (input, init) => {
        if (!descriptor) throw new TypeError("connection refused");
        const url = String(input);
        if (url.endsWith("/v1/health")) return jsonResponse(health(descriptor));
        if (url.endsWith("/v1/models")) {
          const authorization = new Headers(init?.headers).get("authorization");
          return authorization === `Bearer ${TOKEN}`
            ? jsonResponse({ models: [] })
            : jsonResponse({ error: "unauthorized" }, 401);
        }
        return jsonResponse({}, 404);
      };
      const spawnDetached = (): ChildProcess => {
        spawnCount += 1;
        descriptor = {
          pid: 4242,
          instance_id: "instance-1",
          base_url: "http://127.0.0.1:8741",
          service_version: RELEASE,
          protocol_version: 1,
          data_dir: dataDir,
          started_at: "2026-08-11T00:00:00Z",
        };
        mkdirSync(dirname(descriptorPath), { recursive: true });
        writeFileSync(descriptorPath, JSON.stringify(descriptor));
        return new EventEmitter() as ChildProcess;
      };

      const [first, second] = await Promise.all([
        resolveUserService({
          token: TOKEN,
          env,
          fetchImpl,
          spawnDetached,
          expectedRelease: RELEASE,
          waitMs: 2_000,
        }),
        resolveUserService({
          token: TOKEN,
          env,
          fetchImpl,
          spawnDetached,
          expectedRelease: RELEASE,
          waitMs: 2_000,
        }),
      ]);

      assert.equal(spawnCount, 1);
      assert.equal(first.descriptor?.instance_id, "instance-1");
      assert.equal(second.descriptor?.instance_id, "instance-1");
      assert.deepEqual(new Set([first.source, second.source]), new Set(["started", "existing"]));
    });
  });

  it("builds cwd-independent uv arguments from an absolute project", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-command-"));
    const project = join(root, "typed-code-source");
    await mkdir(project);
    await writeFile(join(project, "pyproject.toml"), "[project]\nname='fixture'\n");
    try {
      const canonicalProject = await realpath(project);
      const command = resolveServerCommand({
        env: {
          HOME: root,
          XDG_CONFIG_HOME: join(root, "config"),
          XDG_DATA_HOME: join(root, "data"),
          TYPED_CODE_SERVER_PROJECT: project,
        },
        baseUrl: "http://127.0.0.1:9911",
        expectedRelease: RELEASE,
      });
      assert.equal(command.command, "uv");
      assert.equal(command.kind, "development-project");
      assert.deepEqual(command.args, [
        "run",
        "--project",
        canonicalProject,
        "typed-code",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        "9911",
      ]);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  it("requires absolute live development paths and prefers an executable", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-command-"));
    const executable = join(root, "typed-code-server");
    await writeFile(executable, "#!/bin/sh\nexit 0\n");
    await chmod(executable, 0o755);
    try {
      const command = resolveServerCommand({
        env: {
          HOME: root,
          XDG_CONFIG_HOME: join(root, "config"),
          XDG_DATA_HOME: join(root, "data"),
          TYPED_CODE_SERVER_EXECUTABLE: executable,
          TYPED_CODE_SERVER_PROJECT: join(root, "missing-project"),
        },
        expectedRelease: RELEASE,
      });
      assert.equal(command.command, await realpath(executable));
      assert.equal(command.kind, "executable");

      assert.throws(
        () =>
          resolveServerCommand({
            env: {
              HOME: root,
              XDG_CONFIG_HOME: join(root, "config"),
              XDG_DATA_HOME: join(root, "data"),
              TYPED_CODE_SERVER_PROJECT: join(root, "missing-project"),
            },
            expectedRelease: RELEASE,
          }),
        /development source project does not exist/,
      );
      assert.throws(
        () =>
          resolveServerCommand({
            env: {
              HOME: root,
              XDG_CONFIG_HOME: join(root, "config"),
              XDG_DATA_HOME: join(root, "data"),
              TYPED_CODE_SERVER_PROJECT: "relative/source",
            },
            expectedRelease: RELEASE,
          }),
        /must be an absolute path/,
      );
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });

  it("classifies unauthorized, protocol, release, legacy, and unrelated endpoints", async () => {
    const descriptor: ServiceDescriptor = {
      pid: 42,
      instance_id: "probe-instance",
      base_url: "http://127.0.0.1:8741",
      service_version: RELEASE,
      protocol_version: 1,
      data_dir: "/tmp/probe",
      started_at: "2026-08-11T00:00:00Z",
    };
    assert.equal(
      await probeService(
        descriptor.base_url,
        TOKEN,
        fakeServiceFetch(health(descriptor), 401),
        RELEASE,
      ),
      "unauthorized",
    );
    assert.equal(
      await probeService(
        descriptor.base_url,
        TOKEN,
        fakeServiceFetch({ ...health(descriptor), protocol_version: 2 }),
        RELEASE,
      ),
      "protocol_mismatch",
    );
    assert.equal(
      await probeService(
        descriptor.base_url,
        TOKEN,
        fakeServiceFetch(
          health({ ...descriptor, service_version: "9.9.9" }),
        ),
        RELEASE,
      ),
      "release_mismatch",
    );
    assert.equal(
      await probeService(
        descriptor.base_url,
        TOKEN,
        fakeServiceFetch({
          status: "ok",
          protocol_version: 1,
          providers: {},
          bash: { ready: true },
        }),
        RELEASE,
      ),
      "legacy_service",
    );
    assert.equal(
      await probeService(
        descriptor.base_url,
        TOKEN,
        async () => new Response("<html>not typed-code</html>"),
        RELEASE,
      ),
      "unreachable",
    );
  });

  it("uses an explicit compatible external service without spawning", async () => {
    const descriptor: ServiceDescriptor = {
      pid: 43,
      instance_id: "external-instance",
      base_url: "http://127.0.0.1:9988",
      service_version: RELEASE,
      protocol_version: 1,
      data_dir: "/external/data",
      started_at: "2026-08-11T00:00:00Z",
    };
    let spawnCount = 0;
    const result = await resolveUserService({
      token: TOKEN,
      baseUrl: descriptor.base_url,
      external: true,
      fetchImpl: fakeServiceFetch(health(descriptor)),
      spawnDetached: () => {
        spawnCount += 1;
        return new EventEmitter() as ChildProcess;
      },
      expectedRelease: RELEASE,
    });
    assert.equal(result.source, "external");
    assert.equal(result.baseUrl, descriptor.base_url);
    assert.equal(result.descriptor, null);
    assert.equal(spawnCount, 0);
  });

  it("rejects an unrelated live service and an absent backend", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-boundary-"));
    const env: NodeJS.ProcessEnv = {
      HOME: root,
      XDG_CONFIG_HOME: join(root, "config"),
      XDG_DATA_HOME: join(root, "data"),
    };
    const unrelated: ServiceDescriptor = {
      pid: 44,
      instance_id: "unrelated-instance",
      base_url: "http://127.0.0.1:8741",
      service_version: RELEASE,
      protocol_version: 1,
      data_dir: join(root, "different-data"),
      started_at: "2026-08-11T00:00:00Z",
    };
    try {
      await assert.rejects(
        resolveUserService({
          token: TOKEN,
          env,
          fetchImpl: fakeServiceFetch(health(unrelated)),
          expectedRelease: RELEASE,
          waitMs: 100,
        }),
        /belongs to data directory/,
      );
      await assert.rejects(
        resolveUserService({
          token: TOKEN,
          env,
          fetchImpl: async () => {
            throw new TypeError("connection refused");
          },
          expectedRelease: RELEASE,
          platform: "linux",
          arch: "x64",
          waitMs: 100,
        }),
        /unsupported typed-code service target linux\/x64/,
      );
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
});
