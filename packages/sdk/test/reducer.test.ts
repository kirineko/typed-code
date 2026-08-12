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
    assert.equal(state.snapshot?.transcript.at(-1)?.type, "tool_call");
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
      baseSnapshot({
        phase: "running",
        active_run: {
          run_id: "r1",
          status: "running",
          prompt_preview: "hi",
          started_at: "t",
        },
      }),
    );
    state = applyEvent(
      state,
      env(1, "run.completed", { type: "run.completed", run_id: "r1" }),
    );
    assert.equal(state.phase, "idle");
    assert.equal(state.snapshot?.active_run, null);
  });

  it("drops incomplete stream buffers when a run terminates", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    state = applyEvent(
      state,
      env(1, "message.assistant.delta", {
        type: "message.assistant.delta",
        message_id: "partial",
        delta: "unfinished",
      }),
    );
    state = applyEvent(
      state,
      env(2, "thinking.delta", {
        type: "thinking.delta",
        thinking_id: "thought",
        delta: "unfinished",
      }),
    );
    state = applyEvent(
      state,
      env(3, "run.cancelled", { type: "run.cancelled", run_id: "r1" }),
    );

    assert.deepEqual(state.assistantBuffers, {});
    assert.deepEqual(state.thinkingBuffers, {});
  });

  it("retains a stable named tool through failure", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    state = applyEvent(
      state,
      env(1, "tool.started", {
        type: "tool.started",
        tool_call_id: "tc1",
        tool_name: "bash",
        summary: "run tests",
      }),
    );
    state = applyEvent(
      state,
      env(2, "tool.failed", {
        type: "tool.failed",
        tool_call_id: "tc1",
        summary: "tests failed",
      }),
    );

    assert.deepEqual(state.tools.tc1, {
      tool_call_id: "tc1",
      tool_name: "bash",
      summary: "run tests",
      status: "failed",
    });
    assert.equal(
      state.snapshot?.transcript.find((item) => item.type === "tool_call")?.summary,
      "run tests",
    );
    assert.equal(
      state.snapshot?.transcript.find((item) => item.type === "tool_result")?.summary,
      "tests failed",
    );
  });

  it("keeps the web search query when the result summary arrives", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    state = applyEvent(
      state,
      env(1, "tool.started", {
        type: "tool.started",
        tool_call_id: "ws_1",
        tool_name: "web_search",
        summary: "search 糯糯",
      }),
    );
    state = applyEvent(
      state,
      env(2, "tool.completed", {
        type: "tool.completed",
        tool_call_id: "ws_1",
        summary: "search completed",
        ok: true,
      }),
    );

    assert.deepEqual(state.tools.ws_1, {
      tool_call_id: "ws_1",
      tool_name: "web_search",
      summary: "search 糯糯",
      status: "completed",
    });
    const types = state.snapshot?.transcript.map((item) => item.type);
    assert.deepEqual(types, ["tool_call", "tool_result"]);
  });

  it("applies replay reset snapshot and rejects older events", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    state = applyEvent(
      state,
      env(5, "replay.reset", {
        type: "replay.reset",
        reason: "retention",
        snapshot: baseSnapshot({
          revision: 4,
          latest_event_sequence: 5,
          transcript: [
            {
              type: "assistant_message",
              id: "message-1",
              created_at: "t1",
              text: "replayed",
            },
          ],
        }),
      }),
    );
    const duplicate = applyEvent(
      state,
      env(4, "message.assistant.delta", {
        type: "message.assistant.delta",
        message_id: "old",
        delta: "ignored",
      }),
    );

    assert.equal(state.snapshot?.revision, 4);
    assert.equal(state.snapshot?.transcript.length, 1);
    assert.equal(duplicate, state);
  });
  it("retains a named tool lifecycle when approval events are the only tool signal", () => {
    let state = applySnapshot(createSessionViewState(), baseSnapshot());
    state = applyEvent(
      state,
      env(1, "approval.requested", {
        type: "approval.requested",
        approval: {
          approval_id: "approval-1",
          run_id: "run-1",
          tool_name: "bash",
          summary: "printf smoke-ok",
          status: "pending",
          created_at: "t",
        },
      }),
    );
    assert.equal(state.tools["approval:approval-1"]?.tool_name, "bash");
    assert.equal(state.tools["approval:approval-1"]?.status, "started");

    state = applyEvent(
      state,
      env(2, "approval.resolved", {
        type: "approval.resolved",
        approval_id: "approval-1",
        decision: "approve",
      }),
    );
    assert.equal(state.tools["approval:approval-1"]?.status, "running");

    state = applyEvent(
      state,
      env(3, "run.completed", {
        type: "run.completed",
        run_id: "run-1",
      }),
    );
    assert.equal(state.tools["approval:approval-1"]?.status, "completed");
  });

});
