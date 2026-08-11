import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  canSubmit,
  formatStatusLine,
  formatTranscriptItem,
  isRunActive,
} from "../src/index.ts";
import { createSessionViewState, type SessionSnapshot } from "@typed-code/sdk";
import { applySnapshot } from "@typed-code/sdk";

function snap(phase: SessionSnapshot["phase"] = "idle"): SessionSnapshot {
  return {
    protocol_version: 1,
    session_id: "s1",
    revision: 1,
    phase,
    workspace_path: "/ws",
    provider: "cliproxy",
    model: "m1",
    pending_approvals: [],
    transcript: [],
    created_at: "t",
    updated_at: "t",
    latest_event_sequence: 0,
  };
}

describe("format helpers", () => {
  it("formats status line", () => {
    let view = createSessionViewState();
    view = applySnapshot(view, snap("idle"));
    view = {
      ...view,
      connection: "live",
      lastSequence: 3,
      lastUsage: { total_tokens: 100 },
      contextBudget: 272_000,
    };
    const line = formatStatusLine(view);
    assert.match(line, /typed-code/);
    assert.match(line, /phase=idle/);
    assert.match(line, /conn=live/);
    assert.match(line, /cliproxy\/m1/);
    assert.match(line, /tokens≈100\/272000/);
  });

  it("formats transcript items", () => {
    assert.equal(
      formatTranscriptItem({
        type: "user_message",
        id: "1",
        created_at: "t",
        text: "hi",
      }),
      "you: hi",
    );
    assert.match(
      formatTranscriptItem({
        type: "tool_call",
        id: "2",
        created_at: "t",
        tool_name: "bash",
        summary: "ls",
        status: "started",
      }),
      /tool bash/,
    );
  });

  it("gates submit on idle", () => {
    let view = applySnapshot(createSessionViewState(), snap("idle"));
    view = { ...view, connection: "live" };
    assert.equal(canSubmit(view), true);
    view = applySnapshot(view, snap("running"));
    assert.equal(canSubmit(view), false);
    assert.equal(isRunActive(view), true);
  });
});
