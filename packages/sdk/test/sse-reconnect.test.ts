import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { createClient, type EventEnvelope, type SessionSnapshot } from "../src/index.ts";

function sseBody(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i >= frames.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(frames[i]));
      i += 1;
    },
  });
}

describe("streamEvents", () => {
  it("delivers events and tracks lastSequence", async () => {
    const event: EventEnvelope = {
      protocol_version: 1,
      sequence: 1,
      timestamp: "t",
      session_id: "s1",
      type: "run.started",
      data: { type: "run.started", run_id: "r1", prompt_preview: "hi" },
    };
    const frame = `id: 1\nevent: run.started\ndata: ${JSON.stringify(event)}\n\n`;

    let calls = 0;
    const fetchImpl: typeof fetch = async () => {
      calls += 1;
      return new Response(sseBody([frame]), {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    };

    const client = createClient({
      baseUrl: "http://test",
      token: "tok",
      fetch: fetchImpl,
    });

    const seen: EventEnvelope[] = [];
    const sub = client.streamEvents("s1", {
      after: 0,
      onEvent: (e) => seen.push(e),
      onReset: () => {},
      backoffMs: { initial: 10, max: 10 },
    });

    await waitFor(() => seen.length >= 1, 1000);
    assert.equal(seen[0]?.sequence, 1);
    assert.equal(sub.lastSequence, 1);
    sub.close();
    assert.ok(calls >= 1);
  });

  it("reconnects from the last contiguous sequence after a gap", async () => {
    const makeFrame = (sequence: number) => {
      const event: EventEnvelope = {
        protocol_version: 1,
        sequence,
        timestamp: "t",
        session_id: "s1",
        type: "run.started",
        data: { type: "run.started", run_id: "r1", prompt_preview: "hi" },
      };
      return `id: ${sequence}\ndata: ${JSON.stringify(event)}\n\n`;
    };

    let calls = 0;
    const fetchImpl: typeof fetch = async () => {
      calls += 1;
      return new Response(sseBody([makeFrame(calls === 1 ? 2 : 1)]), {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    };
    const client = createClient({
      baseUrl: "http://test",
      token: "tok",
      fetch: fetchImpl,
    });
    const seen: EventEnvelope[] = [];
    const errors: unknown[] = [];
    const sub = client.streamEvents("s1", {
      after: 0,
      onEvent: (event) => seen.push(event),
      onReset: () => {},
      onError: (error) => errors.push(error),
      backoffMs: { initial: 5, max: 5 },
    });

    await waitFor(() => seen.length === 1, 1000);
    assert.equal(seen[0]?.sequence, 1);
    assert.equal(sub.lastSequence, 1);
    assert.ok(errors.some((error) => String(error).includes("SSE sequence gap")));
    assert.ok(calls >= 2);
    sub.close();
  });

  it("handles replay.reset via onReset", async () => {
    const snapshot: SessionSnapshot = {
      protocol_version: 1,
      session_id: "s1",
      revision: 5,
      phase: "idle",
      workspace_path: "/ws",
      provider: "cliproxy",
      model: "m",
      pending_approvals: [],
      transcript: [],
      created_at: "t",
      updated_at: "t",
      latest_event_sequence: 9,
    };
    const resetEvent: EventEnvelope = {
      protocol_version: 1,
      sequence: 9,
      timestamp: "t",
      session_id: "s1",
      type: "replay.reset",
      data: { type: "replay.reset", snapshot },
    };
    const frame = `data: ${JSON.stringify(resetEvent)}\n\n`;

    let resets = 0;
    const fetchImpl: typeof fetch = async () =>
      new Response(sseBody([frame]), {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });

    const client = createClient({
      baseUrl: "http://test",
      token: "tok",
      fetch: fetchImpl,
    });

    const sub = client.streamEvents("s1", {
      after: 0,
      onEvent: () => {},
      onReset: (snap) => {
        resets += 1;
        assert.equal(snap.latest_event_sequence, 9);
      },
      backoffMs: { initial: 10, max: 10 },
    });

    await waitFor(() => resets >= 1, 1000);
    assert.equal(sub.lastSequence, 9);
    sub.close();
  });

  it("close stops further work", async () => {
    let fetches = 0;
    const fetchImpl: typeof fetch = async () => {
      fetches += 1;
      await new Promise((r) => setTimeout(r, 50));
      return new Response(sseBody([]), { status: 200 });
    };
    const client = createClient({
      baseUrl: "http://test",
      token: "tok",
      fetch: fetchImpl,
    });
    const sub = client.streamEvents("s1", {
      onEvent: () => {},
      onReset: () => {},
      backoffMs: { initial: 5, max: 5 },
    });
    sub.close();
    await new Promise((r) => setTimeout(r, 80));
    // At most one in-flight fetch may have started
    assert.ok(fetches <= 1);
  });
});

async function waitFor(pred: () => boolean, ms: number): Promise<void> {
  const start = Date.now();
  while (!pred()) {
    if (Date.now() - start > ms) {
      throw new Error("timeout waiting for condition");
    }
    await new Promise((r) => setTimeout(r, 10));
  }
}
