import assert from "node:assert/strict";
import { spawn } from "node:child_process";
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
});
