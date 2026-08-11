import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type {
  EventSubscription,
  SessionSnapshot,
  TypedCodeClient,
} from "@typed-code/sdk";

import { AppSessionCoordinator, type DraftSession } from "../src/app-session.ts";

function snapshot(overrides: Partial<SessionSnapshot> = {}): SessionSnapshot {
  return {
    protocol_version: 1,
    session_id: "session-1",
    revision: 1,
    phase: "idle",
    workspace_path: "/workspace",
    provider: "cliproxy",
    model: "model-1",
    pending_approvals: [],
    transcript: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    latest_event_sequence: 0,
    ...overrides,
  };
}

interface ClientControls {
  calls: string[];
  failCreate: boolean;
  failTurn: boolean;
  turnReasoning?: Array<string | null | undefined>;
}

function mockClient(controls: ClientControls): TypedCodeClient {
  const current = snapshot();
  const subscription: EventSubscription = { close() {} };
  return {
    protocolVersion: 1,
    baseUrl: "http://test",
    async getHealth() {
      return {
        status: "ok",
        protocol_version: 1,
        providers: {},
        bash: { ready: true },
      };
    },
    async listModels() {
      return { models: [] };
    },
    async listSessions() {
      return { sessions: [] };
    },
    async createSession() {
      controls.calls.push("create");
      if (controls.failCreate) throw new Error("create failed");
      return { snapshot: current };
    },
    async getSession() {
      controls.calls.push("get");
      return current;
    },
    async createTurn(_sessionId, body) {
      controls.calls.push("turn");
      controls.turnReasoning?.push(body.reasoning_level);
      if (controls.failTurn) throw new Error("turn failed");
      return { run_id: "run-1", revision: 2, phase: "running", status: "accepted" };
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
      controls.calls.push("stream");
      return subscription;
    },
  };
}

function draft(): DraftSession {
  return {
    workspace: "/workspace",
    provider: "cliproxy",
    model: "model-1",
    contextBudget: 272_000,
    reasoningLevel: "high",
  };
}

describe("AppSessionCoordinator", () => {
  it("does not persist an unused draft", () => {
    const controls = { calls: [], failCreate: false, failTurn: false };
    const coordinator = new AppSessionCoordinator(mockClient(controls), draft());

    coordinator.dispose();

    assert.deepEqual(controls.calls, []);
    assert.equal(coordinator.state.kind, "draft");
  });

  it("creates, attaches, and submits exactly once on first prompt", async () => {
    const controls: ClientControls = {
      calls: [],
      failCreate: false,
      failTurn: false,
      turnReasoning: [],
    };
    const coordinator = new AppSessionCoordinator(mockClient(controls), draft());

    await coordinator.submit("hello");

    assert.equal(coordinator.state.kind, "attached");
    assert.deepEqual(controls.calls, ["create", "get", "stream", "turn", "get"]);
    assert.deepEqual(controls.turnReasoning, ["high"]);
  });

  it("returns to the same draft when creation fails", async () => {
    const controls = { calls: [], failCreate: true, failTurn: false };
    const coordinator = new AppSessionCoordinator(mockClient(controls), draft());

    await assert.rejects(coordinator.submit("hello"), /create failed/);

    assert.equal(coordinator.state.kind, "draft");
    assert.equal(coordinator.draft.model, "model-1");
  });

  it("remains attached when the first turn fails after creation", async () => {
    const controls = { calls: [], failCreate: false, failTurn: true };
    const coordinator = new AppSessionCoordinator(mockClient(controls), draft());

    await assert.rejects(coordinator.submit("hello"), /turn failed/);

    assert.equal(coordinator.state.kind, "attached");
    assert.equal(controls.calls.filter((call) => call === "create").length, 1);
  });

  it("resumes explicitly and returns to a launch-workspace draft", async () => {
    const controls = { calls: [], failCreate: false, failTurn: false };
    const coordinator = new AppSessionCoordinator(mockClient(controls), draft());

    await coordinator.resume("session-1");
    assert.equal(coordinator.state.kind, "attached");

    coordinator.newDraft();
    assert.equal(coordinator.state.kind, "draft");
    assert.equal(coordinator.draft.workspace, "/workspace");
  });
});
