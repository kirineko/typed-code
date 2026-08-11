import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { SseParser } from "../src/index.ts";

describe("SseParser", () => {
  it("parses complete frames", () => {
    const p = new SseParser();
    const frames = p.push(
      'id: 1\nevent: run.started\ndata: {"sequence":1,"type":"run.started"}\n\n',
    );
    assert.equal(frames.length, 1);
    assert.equal(frames[0]?.id, "1");
    assert.equal(frames[0]?.event, "run.started");
    assert.match(frames[0]?.data ?? "", /run.started/);
  });

  it("handles fragmented chunks", () => {
    const p = new SseParser();
    assert.equal(p.push("id: 2\n").length, 0);
    assert.equal(p.push("data: {\"a\":1").length, 0);
    const frames = p.push("}\n\n");
    assert.equal(frames.length, 1);
    assert.equal(frames[0]?.data, '{"a":1}');
  });

  it("ignores keepalives and comments", () => {
    const p = new SseParser();
    const frames = p.push(": keepalive\n\ndata: hi\n\n");
    assert.equal(frames.length, 1);
    assert.equal(frames[0]?.data, "hi");
  });

  it("joins multi-line data", () => {
    const p = new SseParser();
    const frames = p.push("data: {\"x\":\ndata: 1}\n\n");
    assert.equal(frames.length, 1);
    assert.equal(frames[0]?.data, '{"x":\n1}');
  });
});
