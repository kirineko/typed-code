import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { stripTerminalSequences } from "@earendil-works/pi-tui";
import {
  applySnapshot,
  createSessionViewState,
  type EventSubscription,
  type SessionSnapshot,
  type TypedCodeClient,
} from "@typed-code/sdk";

import { AppSessionCoordinator } from "../src/app-session.ts";
import { StatusFooter, formatTokenCount } from "../src/components/status-footer.ts";

function snapshot(): SessionSnapshot {
  return {
    protocol_version: 1,
    session_id: "session-1",
    revision: 1,
    phase: "running",
    workspace_path: "/workspace",
    provider: "cliproxy",
    model: "model-1",
    pending_approvals: [],
    transcript: [],
    created_at: "t",
    updated_at: "t",
    latest_event_sequence: 1,
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
      return { models: [] };
    },
    async listSessions() {
      return { sessions: [] };
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

function coordinator(): AppSessionCoordinator {
  return new AppSessionCoordinator(client(), {
    workspace: "/workspace",
    provider: "cliproxy",
    model: "model-1",
    contextBudget: 272_000,
  });
}

describe("responsive status footer", () => {
  it("formats confirmed token counts compactly", () => {
    assert.equal(formatTokenCount(null), "—");
    assert.equal(formatTokenCount(999), "999");
    assert.equal(formatTokenCount(12_345), "12k");
    assert.equal(formatTokenCount(1_250_000), "1.3m");
  });

  it("shows an unavailable value for a draft with a known budget", () => {
    const session = coordinator();
    const footer = new StatusFooter();
    footer.setState(session.state);

    const text = stripTerminalSequences(footer.render(80).join("\n"));

    assert.match(text, /draft/);
    assert.match(text, /ctx —\/272k/);
  });

  it("retains confirmed usage and labels a running turn as pending", () => {
    const session = coordinator();
    session.controller.view = {
      ...applySnapshot(createSessionViewState(), snapshot()),
      connection: "reconnecting",
      contextBudget: 272_000,
      lastUsage: {
        input_tokens: 31_800,
        output_tokens: 2_400,
        total_tokens: 34_200,
      },
    };
    session.state = {
      kind: "attached",
      draft: session.draft,
      controller: session.controller,
    };
    const footer = new StatusFooter();
    footer.setState(session.state);

    const wide = stripTerminalSequences(footer.render(120).join("\n"));
    const narrow = stripTerminalSequences(footer.render(45).join("\n"));

    assert.match(wide, /reconnecting/);
    assert.match(wide, /ctx 34k\/272k · 12\.6%/);
    assert.match(wide, /in 32k · out 2\.4k/);
    assert.match(wide, /usage pending/);
    assert.ok(narrow.length < wide.length);
  });
});
