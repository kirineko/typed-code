import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  applySnapshot,
  createSessionViewState,
  type SessionSnapshot,
  type SessionViewState,
} from "@typed-code/sdk";

import { deriveAgentActivity } from "../src/activity.ts";

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
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    latest_event_sequence: 0,
  };
}

function view(overrides: Partial<SessionViewState> = {}): SessionViewState {
  return {
    ...applySnapshot(createSessionViewState(), snapshot()),
    connection: "live",
    ...overrides,
  };
}

describe("deriveAgentActivity", () => {
  it("distinguishes draft and creating state", () => {
    assert.equal(deriveAgentActivity({ kind: "draft" }).kind, "ready");
    assert.equal(deriveAgentActivity({ kind: "creating" }).kind, "creating");
  });

  it("prioritizes approval over tool, response, and thinking", () => {
    const current = view({
      snapshot: {
        ...snapshot(),
        phase: "awaiting_approval",
        pending_approvals: [
          {
            approval_id: "approval-1",
            run_id: "run-1",
            tool_name: "bash",
            summary: "run tests",
            status: "pending",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
      },
      tools: {
        "tool-1": {
          tool_call_id: "tool-1",
          tool_name: "bash",
          summary: "run tests",
          status: "running",
        },
      },
      assistantBuffers: { message: "answer" },
      thinkingBuffers: { thinking: "reason" },
    });

    const activity = deriveAgentActivity({ kind: "attached", view: current });

    assert.equal(activity.kind, "awaiting_approval");
    assert.match(activity.detail ?? "", /bash/);
  });

  it("prioritizes a named tool over buffered content", () => {
    const current = view({
      tools: {
        tool: {
          tool_call_id: "tool",
          tool_name: "read",
          summary: "app.ts",
          status: "started",
        },
      },
      assistantBuffers: { message: "answer" },
    });

    const activity = deriveAgentActivity({ kind: "attached", view: current });

    assert.equal(activity.kind, "calling_tool");
    assert.equal(activity.label, "Calling read");
  });

  it("does not repeat a tool name when the service summary is only its label", () => {
    const approvalActivity = deriveAgentActivity({
      kind: "attached",
      view: view({
        snapshot: {
          ...snapshot(),
          phase: "awaiting_approval",
          pending_approvals: [
            {
              approval_id: "approval-1",
              run_id: "run-1",
              tool_name: "bash",
              summary: "bash:",
              status: "pending",
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        },
      }),
    });
    const toolActivity = deriveAgentActivity({
      kind: "attached",
      view: view({
        tools: {
          tool: {
            tool_call_id: "tool",
            tool_name: "bash",
            summary: "bash:",
            status: "running",
          },
        },
      }),
    });

    assert.equal(approvalActivity.detail, "bash");
    assert.equal(toolActivity.detail, undefined);
  });

  it("shows finalizing between the completed message and terminal run event", () => {
    const activity = deriveAgentActivity({
      kind: "attached",
      view: view({
        phase: "running",
        lastEvent: {
          protocol_version: 1,
          sequence: 3,
          timestamp: "t",
          session_id: "session-1",
          type: "message.assistant.done",
          data: {
            type: "message.assistant.done",
            message_id: "message-1",
            text: "done",
          },
        },
      }),
    });

    assert.equal(activity.kind, "finalizing");
    assert.equal(activity.label, "Finalizing");
  });

  it("distinguishes responding, thinking, preparing, and failure", () => {
    assert.equal(
      deriveAgentActivity({
        kind: "attached",
        view: view({ assistantBuffers: { message: "answer" } }),
      }).kind,
      "responding",
    );
    assert.equal(
      deriveAgentActivity({
        kind: "attached",
        view: view({ thinkingBuffers: { thinking: "reason" } }),
      }).kind,
      "thinking",
    );
    assert.equal(
      deriveAgentActivity({ kind: "attached", view: view() }).kind,
      "preparing",
    );
    assert.equal(
      deriveAgentActivity({
        kind: "attached",
        view: view({ error: { code: "run_failed", message: "failed" } }),
      }).kind,
      "failed",
    );
  });

  it("keeps connection state independent from run activity", () => {
    const activity = deriveAgentActivity({
      kind: "attached",
      view: view({
        connection: "reconnecting",
        tools: {
          tool: {
            tool_call_id: "tool",
            tool_name: "bash",
            summary: "running",
            status: "running",
          },
        },
      }),
    });

    assert.equal(activity.kind, "calling_tool");
    assert.equal(activity.connection, "reconnecting");
  });
});
