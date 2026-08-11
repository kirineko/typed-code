import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { parseArgs, validateFlags } from "../src/index.ts";

describe("config", () => {
  it("parses flags", () => {
    const flags = parseArgs([
      "--token",
      "abc",
      "--base-url",
      "http://localhost:9",
      "--new",
      "--provider",
      "deepseek",
    ]);
    assert.equal(flags.token, "abc");
    assert.equal(flags.baseUrl, "http://localhost:9");
    assert.equal(flags.createNew, true);
    assert.equal(flags.provider, "deepseek");
  });

  it("allows missing token on argv (filled from credentials later)", () => {
    const flags = parseArgs(["--workspace", "/tmp"]);
    assert.equal(validateFlags(flags), null);
    assert.equal(flags.token, "");
  });

  it("parses --no-spawn", () => {
    const flags = parseArgs(["--no-spawn", "--token", "t"]);
    assert.equal(flags.noSpawn, true);
  });
});
