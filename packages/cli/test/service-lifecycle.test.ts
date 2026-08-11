import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { describe, it } from "node:test";

import { stopOwnedService } from "../src/service-lifecycle.js";

describe("owned service lifecycle", () => {
  it("waits for the owned child to exit", async () => {
    const child = spawn(process.execPath, ["-e", "process.stdin.resume()"]);

    await stopOwnedService({
      baseUrl: "http://127.0.0.1:1",
      token: "test",
      owned: true,
      child,
    });

    assert.ok(child.exitCode !== null || child.signalCode !== null);
  });

  it("returns without signaling a child that already exited by signal", async () => {
    const child = spawn(process.execPath, ["-e", "process.stdin.resume()"]);
    const exited = once(child, "exit");
    child.kill("SIGTERM");
    await exited;
    let killCalls = 0;
    child.kill = (() => {
      killCalls += 1;
      return false;
    }) as typeof child.kill;

    await stopOwnedService({
      baseUrl: "http://127.0.0.1:1",
      token: "test",
      owned: true,
      child,
    });

    assert.equal(child.exitCode, null);
    assert.equal(child.signalCode, "SIGTERM");
    assert.equal(killCalls, 0);
  });
});
