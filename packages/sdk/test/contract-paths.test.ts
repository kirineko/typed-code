import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

import { EVENT_TYPES, SDK_HTTP_PATHS } from "../src/index.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");

describe("contract drift", () => {
  it("SDK paths match OpenAPI paths", () => {
    const openapi = JSON.parse(
      readFileSync(join(root, "contracts/openapi.v1.json"), "utf8"),
    ) as { paths: Record<string, unknown> };
    const serverPaths = Object.keys(openapi.paths).sort();
    const sdkPaths = [...SDK_HTTP_PATHS].sort();
    assert.deepEqual(sdkPaths, serverPaths);
  });

  it("SDK event types are non-empty and include core run events", () => {
    assert.ok(EVENT_TYPES.includes("run.started"));
    assert.ok(EVENT_TYPES.includes("run.completed"));
    assert.ok(EVENT_TYPES.includes("message.assistant.delta"));
    assert.ok(EVENT_TYPES.includes("approval.requested"));
    assert.ok(EVENT_TYPES.includes("replay.reset"));
  });
});
