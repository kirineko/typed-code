import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { stripTerminalSequences, visibleWidth } from "@earendil-works/pi-tui";
import {
  applySnapshot,
  createSessionViewState,
  type SessionSnapshot,
  type SessionViewState,
} from "@typed-code/sdk";

import { TranscriptView } from "../src/components/transcript-view.ts";

function snapshot(overrides: Partial<SessionSnapshot> = {}): SessionSnapshot {
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
    ...overrides,
  };
}

function view(overrides: Partial<SessionViewState> = {}): SessionViewState {
  return {
    ...applySnapshot(createSessionViewState(), snapshot()),
    connection: "live",
    ...overrides,
  };
}

describe("TranscriptView reconciliation", () => {
  it("keeps one assistant component across streaming and completion", () => {
    const transcript = new TranscriptView();
    transcript.setView(view({ assistantBuffers: { message: "# Heading\n\n```ts\nconst x" } }));
    const active = transcript.componentForKey("assistant:message");
    const streaming = stripTerminalSequences(transcript.render(60).join("\n"));
    assert.match(streaming, /Agent · responding/);
    assert.match(streaming, /▌/);

    transcript.setView(
      view({
        snapshot: snapshot({
          phase: "idle",
          transcript: [
            {
              type: "assistant_message",
              id: "message",
              created_at: "t",
              text: "# Heading\n\n```ts\nconst x = 1;\n```",
            },
          ],
        }),
      }),
    );

    assert.equal(transcript.componentForKey("assistant:message"), active);
    const rendered = stripTerminalSequences(transcript.render(60).join("\n"));
    assert.match(rendered, /Heading/);
    assert.match(rendered, /const x = 1/);
    assert.doesNotMatch(rendered, /responding|▌/);
  });

  it("collapses completed thinking and expands on request", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        snapshot: snapshot({
          transcript: [
            {
              type: "thinking",
              id: "thought",
              created_at: "t",
              text: "private reasoning summary",
            },
          ],
        }),
      }),
    );

    assert.doesNotMatch(
      stripTerminalSequences(transcript.render(60).join("\n")),
      /private reasoning summary/,
    );
    assert.equal(transcript.toggleThinking("thought"), true);
    assert.match(
      stripTerminalSequences(transcript.render(60).join("\n")),
      /private reasoning summary/,
    );
    assert.equal(transcript.toggleThinking("thought"), true);
    assert.doesNotMatch(
      stripTerminalSequences(transcript.render(60).join("\n")),
      /private reasoning summary/,
    );
  });

  it("lists completed thinking newest first and toggles a selected block", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        snapshot: snapshot({
          transcript: [
            {
              type: "thinking",
              id: "first",
              created_at: "t1",
              text: "first reasoning",
            },
            {
              type: "thinking",
              id: "second",
              created_at: "t2",
              text: "second reasoning",
            },
          ],
        }),
        thinkingBuffers: { active: "live reasoning" },
      }),
    );

    assert.deepEqual(
      transcript.thinkingChoices().map(({ id, label }) => ({ id, label })),
      [
        { id: "second", label: "Thinking 2" },
        { id: "first", label: "Thinking 1" },
      ],
    );
    assert.equal(transcript.toggleThinking("first"), true);
    const rendered = stripTerminalSequences(transcript.render(60).join("\n"));
    assert.match(rendered, /first reasoning/);
    assert.doesNotMatch(rendered, /second reasoning/);
    assert.equal(transcript.collapseExpandedThinking(), true);
    assert.doesNotMatch(
      stripTerminalSequences(transcript.render(60).join("\n")),
      /first reasoning/,
    );
  });

  it("keeps a named tool block through lifecycle updates", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        tools: {
          tool: {
            tool_call_id: "tool",
            tool_name: "bash",
            summary: "running tests",
            status: "running",
          },
        },
      }),
    );
    const active = transcript.componentForKey("tool:tool");

    transcript.setView(
      view({
        tools: {
          tool: {
            tool_call_id: "tool",
            tool_name: "bash",
            summary: "tests failed",
            status: "failed",
          },
        },
      }),
    );

    assert.equal(transcript.componentForKey("tool:tool"), active);
    assert.match(
      stripTerminalSequences(transcript.render(50).join("\n")),
      /bash.*tests failed.*failed/,
    );
  });

  it("keeps committed tools above later assistant text instead of repeating them at the end", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        snapshot: snapshot({
          transcript: [
            {
              type: "user_message",
              id: "user",
              created_at: "t",
              text: "查一下糯糯",
            },
            {
              type: "thinking",
              id: "thought",
              created_at: "t",
              text: "先确认角色再搜索",
            },
            {
              type: "tool_call",
              id: "ws_1",
              created_at: "t",
              tool_name: "web_search",
              summary: "search 糯糯",
              status: "completed",
            },
            {
              type: "assistant_message",
              id: "assistant",
              created_at: "t",
              text: "糯糯是弗洛洛的二创称呼。",
            },
          ],
        }),
        tools: {
          ws_1: {
            tool_call_id: "ws_1",
            tool_name: "web_search",
            summary: "search completed",
            status: "completed",
          },
        },
      }),
    );

    const rendered = stripTerminalSequences(transcript.render(80).join("\n"));
    const toolAt = rendered.indexOf("web_search");
    const answerAt = rendered.indexOf("糯糯是弗洛洛");
    assert.ok(toolAt >= 0 && answerAt > toolAt);
    assert.equal(rendered.split("web_search").length - 1, 1);
  });

  it("renders live thinking and tools before a streaming assistant reply", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        snapshot: snapshot({
          transcript: [
            {
              type: "user_message",
              id: "user",
              created_at: "t",
              text: "查一下糯糯",
            },
          ],
        }),
        thinkingBuffers: { thought: "先确认角色" },
        tools: {
          ws_1: {
            tool_call_id: "ws_1",
            tool_name: "web_search",
            summary: "search 糯糯",
            status: "started",
          },
        },
        assistantBuffers: { assistant: "结合上下文，我先搜一下。" },
      }),
    );

    const rendered = stripTerminalSequences(transcript.render(80).join("\n"));
    const thinkingAt = rendered.indexOf("先确认角色");
    const toolAt = rendered.indexOf("web_search");
    const answerAt = rendered.indexOf("结合上下文");
    assert.ok(thinkingAt >= 0 && toolAt > thinkingAt && answerAt > toolAt);
  });

  it("reconstructs completed web search from snapshot transcript items", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        snapshot: snapshot({
          transcript: [
            {
              type: "tool_call",
              id: "ws_1",
              created_at: "t",
              tool_name: "web_search",
              summary: "search typed-code release",
              status: "completed",
            },
            {
              type: "tool_result",
              id: "ws_1:result",
              created_at: "t",
              tool_call_id: "ws_1",
              ok: true,
              summary: "search completed",
            },
          ],
        }),
      }),
    );

    const rendered = stripTerminalSequences(transcript.render(72).join("\n"));
    assert.match(rendered, /web_search.*search typed-code release.*completed/);
    assert.match(rendered, /Tool result · search completed/);
  });

  it("reflows long Markdown without exceeding terminal width", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        assistantBuffers: {
          message:
            "| Column A | Column B |\n| --- | --- |\n| a very long table cell that must wrap | another long value |",
        },
      }),
    );

    for (const width of [24, 40, 80]) {
      const lines = transcript.render(width);
      assert.ok(lines.every((line) => visibleWidth(line) <= width));
    }
  });
  it("renders compact message ownership and deduplicated tool labels", () => {
    const transcript = new TranscriptView();
    transcript.setView(
      view({
        snapshot: snapshot({
          transcript: [
            {
              type: "user_message",
              id: "user",
              created_at: "t",
              text: "执行一下 ls 命令",
            },
            {
              type: "assistant_message",
              id: "assistant",
              created_at: "t",
              text: "正在执行。",
            },
            {
              type: "tool_call",
              id: "tool",
              created_at: "t",
              tool_name: "bash",
              summary: "bash:",
              status: "started",
            },
          ],
        }),
      }),
    );

    const lines = transcript.render(48);
    const rendered = stripTerminalSequences(lines.join("\n"));
    assert.match(rendered, /You\s+执行一下 ls 命令/);
    assert.match(rendered, /◆ Agent/);
    assert.doesNotMatch(rendered, /bash\s+·\s+bash:/);
    assert.ok(lines.every((line) => visibleWidth(line) <= 48));
    assert.ok(!rendered.includes("\n\n\n"));
  });

});
