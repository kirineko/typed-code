import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { EventSubscription, SessionSnapshot, TypedCodeClient } from "@typed-code/sdk";

import { AppSessionCoordinator } from "../src/app-session.ts";
import { CommandRegistry, type CommandRuntime } from "../src/commands.ts";

function snapshot(): SessionSnapshot {
  return {
    protocol_version: 1,
    session_id: "session-current",
    revision: 1,
    phase: "idle",
    workspace_path: "/project",
    provider: "cliproxy",
    model: "model-1",
    pending_approvals: [],
    transcript: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    latest_event_sequence: 0,
  };
}

function client(): TypedCodeClient {
  const current = snapshot();
  const subscription: EventSubscription = { close() {} };
  return {
    protocolVersion: 1,
    baseUrl: "http://test",
    async getHealth() {
      return { status: "ok", protocol_version: 1, providers: {}, bash: { ready: true } };
    },
    async listModels() {
      return {
        models: [
          {
            provider: "cliproxy",
            model_id: "model-1",
            availability: "available",
            context_token_budget: 272_000,
            capabilities: {
              reasoning_levels: ["none", "low", "medium", "high", "xhigh", "max"],
              default_reasoning_level: "medium",
            },
          },
        ],
      };
    },
    async listSessions() {
      return {
        sessions: [
          {
            session_id: "session-current",
            revision: 1,
            phase: "idle",
            workspace_path: "/project",
            provider: "cliproxy",
            model: "model-1",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          {
            session_id: "session-other",
            revision: 1,
            phase: "idle",
            workspace_path: "/other",
            provider: "cliproxy",
            model: "model-1",
            created_at: "2026-01-02T00:00:00Z",
            updated_at: "2026-01-02T00:00:00Z",
          },
        ],
      };
    },
    async createSession() {
      return { snapshot: current };
    },
    async getSession() {
      return current;
    },
    async createTurn() {
      return { run_id: "run", revision: 2, phase: "running", status: "accepted" };
    },
    async abort() {
      return current;
    },
    async decideApproval() {
      return current;
    },
    async updateSessionModel() {
      return current;
    },
    async reloadConfig() {
      return { reloaded: true, providers: {} };
    },
    streamEvents() {
      return subscription;
    },
  };
}

function runtime() {
  const flashes: string[] = [];
  const remembered: string[] = [];
  const opened = { config: 0, help: 0, resumeAll: false };
  const api = client();
  const session = new AppSessionCoordinator(api, {
    workspace: "/project",
    provider: "cliproxy",
    model: "model-1",
    contextBudget: 272_000,
    reasoningLevel: "high",
  });
  const value: CommandRuntime = {
    client: api,
    session,
    openHelp() {
      opened.help += 1;
    },
    openConfig() {
      opened.config += 1;
    },
    async openModelPicker() {},
    rememberModel(provider, model, reasoningLevel) {
      remembered.push(`${provider}/${model}/${reasoningLevel ?? "default"}`);
    },
    async openResumePicker(allProjects) {
      opened.resumeAll = allProjects;
    },
    openStatus() {},
    openKeys() {},
    quit() {},
    flash(message) {
      flashes.push(message);
    },
  };
  return { value, flashes, opened, remembered };
}

describe("CommandRegistry", () => {
  it("drives help and slash completion from one registry", async () => {
    const fixture = runtime();
    const registry = new CommandRegistry(fixture.value);

    assert.match(registry.helpText(), /\/resume \[--all\|session-prefix\]/);
    assert.deepEqual(
      registry.slashCommands().map((command) => command.name),
      ["help", "model", "config", "new", "resume", "status", "abort", "keys", "quit"],
    );
    const model = registry.slashCommands().find((command) => command.name === "model");
    const completions = await model?.getArgumentCompletions?.("model");
    assert.equal(completions?.[0]?.value, "cliproxy/model-1");
  });

  it("routes aliases and all-project resume", async () => {
    const fixture = runtime();
    const registry = new CommandRegistry(fixture.value);

    await registry.execute("/?");
    await registry.execute("/resume --all");

    assert.equal(fixture.opened.help, 1);
    assert.equal(fixture.opened.resumeAll, true);
  });

  it("refuses inline configuration credentials", async () => {
    const fixture = runtime();
    const registry = new CommandRegistry(fixture.value);

    await registry.execute("/config deepseek sk-secret");

    assert.equal(fixture.opened.config, 0);
    assert.match(fixture.flashes[0] ?? "", /cannot be entered/);
  });

  it("remembers an explicit model selection", async () => {
    const fixture = runtime();
    const registry = new CommandRegistry(fixture.value);

    await registry.execute("/model cliproxy/model-1");

    assert.deepEqual(fixture.remembered, ["cliproxy/model-1/medium"]);
  });

  it("completes only current-project sessions by default", async () => {
    const fixture = runtime();
    const registry = new CommandRegistry(fixture.value);
    const resume = registry.slashCommands().find((command) => command.name === "resume");

    const completions = await resume?.getArgumentCompletions?.("session");

    assert.deepEqual(completions?.map((item) => item.value), ["session-current"]);
  });
});
