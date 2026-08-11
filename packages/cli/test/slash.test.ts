import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  hasAnyProviderKey,
  isSlashCommand,
  parseSimpleToml,
  parseSlash,
  SecretInput,
  slashHelpText,
  shouldRecordInHistory,
} from "../src/index.ts";

describe("slash routing", () => {
  it("detects slash commands", () => {
    assert.equal(isSlashCommand("/help"), true);
    assert.equal(isSlashCommand("  /model"), true);
    assert.equal(isSlashCommand("hello"), false);
    assert.equal(isSlashCommand("/config now"), true);
  });

  it("parses command and args", () => {
    assert.deepEqual(parseSlash("/help"), { command: "/help", args: "" });
    assert.deepEqual(parseSlash("/model gpt"), {
      command: "/model",
      args: "gpt",
    });
  });

  it("help text lists the discoverable command surface", () => {
    const help = slashHelpText();
    assert.match(help, /\/config \[deepseek\|cliproxy\]/);
    assert.match(help, /\/model \[provider\/model\]/);
    assert.match(help, /\/resume \[--all\|session-prefix\]/);
    assert.match(help, /\/new/);
    assert.match(help, /\/status/);
    assert.match(help, /\/abort/);
    assert.match(help, /\/keys/);
    assert.match(help, /\/quit/);
  });

  it("keeps credential commands out of history", () => {
    assert.equal(shouldRecordInHistory("/config show"), false);
    assert.equal(shouldRecordInHistory("/config deepseek sk-secret"), false);
    assert.equal(shouldRecordInHistory("  /CONFIG cliproxy"), false);
    assert.equal(shouldRecordInHistory("/model 0"), true);
  });

  it("masks secret input without changing its value", () => {
    const input = new SecretInput();
    input.setValue("sk-secret-value");
    const rendered = input.render(80).join("\n");

    assert.doesNotMatch(rendered, /sk-secret-value/);
    assert.equal(rendered.match(/\*/g)?.length, 15);
    assert.equal(input.getValue(), "sk-secret-value");
  });

  it("parses multi-arg config lines without advertising inline secrets", () => {
    assert.deepEqual(parseSlash("/config deepseek sk-abc"), {
      command: "/config",
      args: "deepseek sk-abc",
    });
    assert.doesNotMatch(slashHelpText(), /<key>|<api-key>/);
    assert.deepEqual(parseSlash("/model deepseek deepseek-v4-flash"), {
      command: "/model",
      args: "deepseek deepseek-v4-flash",
    });
  });
});

describe("local credentials helpers", () => {
  it("hasAnyProviderKey", () => {
    assert.equal(hasAnyProviderKey({}), false);
    assert.equal(hasAnyProviderKey({ server_token: "x" }), false);
    assert.equal(hasAnyProviderKey({ deepseek_api_key: "k" }), true);
    assert.equal(hasAnyProviderKey({ cliproxy_api_key: "k" }), true);
  });

  it("parses simple toml keys", () => {
    const m = parseSimpleToml(`
# comment
server_token = "abc"
deepseek_api_key = 'sk-test'
`);
    assert.equal(m.server_token, "abc");
    assert.equal(m.deepseek_api_key, "sk-test");
  });
});
