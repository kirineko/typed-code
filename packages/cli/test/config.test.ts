import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, it } from "node:test";

import type { ModelInfo } from "@typed-code/sdk";

import { selectInitialModel } from "../src/app.ts";
import {
  modelPreferencePath,
  parseArgs,
  readModelPreference,
  validateFlags,
  writeModelPreference,
} from "../src/index.ts";

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

describe("model preferences", () => {
  const models: ModelInfo[] = [
    {
      provider: "deepseek",
      model_id: "deepseek-v4-flash",
      availability: "available",
      context_token_budget: 1_000_000,
    },
    {
      provider: "cliproxy",
      model_id: "gpt-5.6-terra",
      availability: "available",
      context_token_budget: 272_000,
    },
  ];

  it("prefers DeepSeek unless a remembered or explicit model is available", () => {
    assert.equal(
      selectInitialModel(models, parseArgs([]), null, "cliproxy", "gpt-5.6-terra")
        ?.provider,
      "deepseek",
    );
    assert.equal(
      selectInitialModel(
        models,
        parseArgs([]),
        { provider: "cliproxy", model: "gpt-5.6-terra" },
        "cliproxy",
        "gpt-5.6-terra",
      )?.provider,
      "cliproxy",
    );
    assert.equal(
      selectInitialModel(
        models,
        parseArgs([]),
        { provider: "cliproxy", model: "removed-model" },
        "cliproxy",
        "gpt-5.6-terra",
      )?.provider,
      "deepseek",
    );
    assert.equal(
      selectInitialModel(
        models,
        parseArgs(["--provider", "cliproxy", "--model", "gpt-5.6-terra"]),
        { provider: "deepseek", model: "deepseek-v4-flash" },
      )?.provider,
      "cliproxy",
    );
  });

  it("persists and restores the latest model selection", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-preference-"));
    const env = { XDG_CONFIG_HOME: root };
    const path = modelPreferencePath(env);
    await mkdir(join(root, "typed-code"), { recursive: true });
    try {
      writeModelPreference(path, {
        provider: "cliproxy",
        model: "gpt-5.6-terra",
        reasoning_level: "xhigh",
      });

      assert.deepEqual(readModelPreference(path), {
        provider: "cliproxy",
        model: "gpt-5.6-terra",
        reasoning_level: "xhigh",
      });
      assert.equal((await stat(path)).mode & 0o777, 0o600);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
});
