import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  applyEvent,
  applySnapshot,
  createSessionViewState,
  type EventEnvelope,
  type SessionSnapshot,
} from "../src/index.ts";

function baseSnapshot(overrides: Partial<SessionSnapshot> = {}): SessionSnapshot {
  return {
    protocol_version: 1,
    session_id: "s1",
    revision: 1,
    phase: "idle",
    workspace_path: "/tmp/ws",
    provider: "cliproxy",
    model: "m",
    pending_approvals: [],
    transcript: [],
    created_at: "t0",
    updated_at: "t0",
    latest_event_sequence: 0,
    ...overrides,
  };
}

function env(
  sequence: number,
  type: EventEnvelope["type"],
  data: EventEnvelope["data"],
): EventEnvelope {
  return {
    protocol_version: 1,
    sequence,
    timestamp: "t",
    session_id: "s1",
    type,
    data,
  };
}

describe("session reducer", () => {
  it("applies snapshot authoritatively", () => {
    let state = createSessionViewState();
    state = applySnapshot(state, baseSnapshot({ latest_event_sequence: 3, revision: 2 }));
    assert.equal(state.lastSequence, 3);
    assert.equal(state.snapshot?.revision, 2);
    assert.equal(state.phase, "idle");
  });

  it("ignores duplicate sequences", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    const e = env(1, "run.started", {
      type: "run.started",
      run_id: "r1",
      prompt_preview: "hi",
    });
    state = applyEvent(state, e);
    const again = applyEvent(state, e);
    assert.equal(again, state);
    assert.equal(state.lastSequence, 1);
  });

  it("buffers assistant deltas then commits on done", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    state = applyEvent(
      state,
      env(1, "message.assistant.delta", {
        type: "message.assistant.delta",
        message_id: "m1",
        delta: "hel",
      }),
    );
    state = applyEvent(
      state,
      env(2, "message.assistant.delta", {
        type: "message.assistant.delta",
        message_id: "m1",
        delta: "lo",
      }),
    );
    assert.equal(state.assistantBuffers.m1, "hello");
    state = applyEvent(
      state,
      env(3, "message.assistant.done", {
        type: "message.assistant.done",
        message_id: "m1",
        text: "hello",
      }),
    );
    assert.equal(state.assistantBuffers.m1, undefined);
    assert.equal(state.snapshot?.transcript.at(-1)?.type, "assistant_message");
  });

  it("tracks tool lifecycle and approvals", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    state = applyEvent(
      state,
      env(1, "tool.started", {
        type: "tool.started",
        tool_call_id: "tc1",
        tool_name: "write_file",
        summary: "write a",
        status: "started",
      }),
    );
    assert.equal(state.tools.tc1?.status, "started");
    state = applyEvent(
      state,
      env(2, "approval.requested", {
        type: "approval.requested",
        approval: {
          approval_id: "ap1",
          run_id: "r1",
          tool_name: "write_file",
          summary: "write a",
          status: "pending",
          created_at: "t",
        },
      }),
    );
    assert.equal(state.phase, "awaiting_approval");
    assert.equal(state.snapshot?.pending_approvals.length, 1);
    state = applyEvent(
      state,
      env(3, "approval.resolved", {
        type: "approval.resolved",
        approval_id: "ap1",
        decision: "approve",
      }),
    );
    assert.equal(state.snapshot?.pending_approvals.length, 0);
  });

  it("sets terminal phase on run.completed", () => {
    let state = applySnapshot(
      createSessionViewState(),
      baseSnapshot({ phase: "running" }),
    );
    state = applyEvent(
      state,
      env(1, "run.completed", { type: "run.completed", run_id: "r1" }),
    );
    assert.equal(state.phase, "idle");
  });
});
