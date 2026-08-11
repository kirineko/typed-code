import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  Editor,
  TuiAltScreen,
  stripTerminalSequences,
  type Terminal,
} from "@earendil-works/pi-tui";
import {
  applySnapshot,
  createSessionViewState,
  type EventSubscription,
  type SessionSnapshot,
  type TypedCodeClient,
} from "@typed-code/sdk";

import { AppSessionCoordinator } from "../src/app-session.ts";
import { AppShell } from "../src/app-shell.ts";
import { InfoDialog } from "../src/components/info-dialog.ts";
import { handleThinkingShortcut } from "../src/interactive-workflows.ts";
import { editorTheme } from "../src/theme.ts";

class FakeTerminal implements Terminal {
  columns = 80;
  rows = 24;
  readonly kittyProtocolActive = false;
  output = "";
  private input: ((data: string) => void) | null = null;
  private resizeListener: (() => void) | null = null;

  start(onInput: (data: string) => void, onResize: () => void): void {
    this.input = onInput;
    this.resizeListener = onResize;
  }

  stop(): void {}
  async drainInput(): Promise<void> {}
  write(data: string): void {
    this.output += data;
  }
  moveBy(): void {}
  hideCursor(): void {}
  showCursor(): void {}
  clearLine(): void {}
  clearFromCursor(): void {}
  clearScreen(): void {}
  setTitle(): void {}
  setProgress(): void {}

  send(data: string): void {
    this.input?.(data);
  }

  resize(columns: number, rows: number): void {
    this.columns = columns;
    this.rows = rows;
    this.resizeListener?.();
  }
}

function snapshot(transcriptCount = 0): SessionSnapshot {
  return {
    protocol_version: 1,
    session_id: "session-1",
    revision: 1,
    phase: "running",
    workspace_path: "/workspace",
    provider: "cliproxy",
    model: "model-1",
    pending_approvals: [],
    transcript: Array.from({ length: transcriptCount }, (_unused, index) => ({
      type: "assistant_message" as const,
      id: `message-${index}`,
      created_at: `t${index}`,
      text: `Message ${index}\n\n${"content ".repeat(6)}`,
    })),
    created_at: "t0",
    updated_at: "t0",
    latest_event_sequence: transcriptCount,
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

function fixture() {
  const terminal = new FakeTerminal();
  const tui = new TuiAltScreen(terminal);
  const editor = new Editor(tui, editorTheme);
  const shell = new AppShell(tui, editor);
  const session = new AppSessionCoordinator(client(), {
    workspace: "/workspace",
    provider: "cliproxy",
    model: "model-1",
    contextBudget: 272_000,
  });
  return { terminal, tui, editor, shell, session };
}

describe("AppShell virtual terminal", () => {
  it("renders a responsive draft shell and restores the terminal", () => {
    const current = fixture();
    current.tui.start();
    current.shell.sync(current.session.state);
    current.tui.renderNow(true);

    const document = stripTerminalSequences(current.tui.render(80).join("\n"));
    assert.match(document, /typed-code/);
    assert.match(document, /NEW/);
    assert.match(document, /new session/i);
    assert.match(document, /ctx —\/272k/);

    current.terminal.resize(42, 10);
    current.tui.renderNow(true);
    assert.equal(current.editor.getText(), "");
    current.tui.stop();
    assert.match(current.terminal.output, /\u001b\[\?1049l/);
  });

  it("preserves manual scrolling and exposes new output", () => {
    const current = fixture();
    current.tui.start();
    current.session.controller.view = {
      ...applySnapshot(createSessionViewState(), snapshot(20)),
      connection: "live",
    };
    current.session.state = {
      kind: "attached",
      draft: current.session.draft,
      controller: current.session.controller,
    };
    current.shell.sync(current.session.state);
    current.tui.renderNow(true);
    current.shell.transcriptScroll.scrollToStart();

    current.session.controller.view = {
      ...current.session.controller.view,
      lastSequence: 21,
      assistantBuffers: { stream: "new content" },
    };
    current.shell.sync(current.session.state);

    assert.match(
      stripTerminalSequences(current.shell.activity.render(80).join("\n")),
      /new output/,
    );
    current.shell.scrollToEnd();
    assert.doesNotMatch(
      stripTerminalSequences(current.shell.activity.render(80).join("\n")),
      /new output/,
    );
    current.tui.stop();
  });

  it("renders approval and reconnecting tool activity independently", () => {
    const current = fixture();
    current.tui.start();
    const pending = {
      ...snapshot(),
      phase: "awaiting_approval" as const,
      pending_approvals: [
        {
          approval_id: "approval-1",
          run_id: "run-1",
          tool_name: "bash",
          summary: "run tests",
          status: "pending" as const,
          created_at: "t",
        },
      ],
    };
    current.session.controller.view = {
      ...applySnapshot(createSessionViewState(), pending),
      connection: "reconnecting",
    };
    current.session.state = {
      kind: "attached",
      draft: current.session.draft,
      controller: current.session.controller,
    };
    current.shell.sync(current.session.state);
    assert.match(
      stripTerminalSequences(current.shell.activity.render(80).join("\n")),
      /Awaiting approval.*bash.*reconnecting/,
    );

    current.session.controller.view = {
      ...current.session.controller.view,
      phase: "running",
      snapshot: { ...pending, phase: "running", pending_approvals: [] },
      tools: {
        tool: {
          tool_call_id: "tool",
          tool_name: "bash",
          summary: "run tests",
          status: "running",
        },
      },
    };
    current.shell.sync(current.session.state);
    assert.match(
      stripTerminalSequences(current.shell.activity.render(80).join("\n")),
      /Calling bash.*reconnecting/,
    );
    current.tui.stop();
  });

  it("owns overlay focus and restores the editor", () => {
    const current = fixture();
    current.tui.start();
    const dialog = new InfoDialog("Help", "Body", () => current.shell.modals.close());
    current.shell.modals.show(dialog, current.editor);

    assert.equal(current.shell.modals.isOpen, true);
    current.terminal.send("\r");
    assert.equal(current.shell.modals.isOpen, false);
    assert.equal(current.editor.focused, true);
    current.tui.stop();
  });

  it("selects a completed thinking block and collapses it on Ctrl+T", () => {
    const current = fixture();
    current.tui.start();
    const thinkingSnapshot: SessionSnapshot = {
      ...snapshot(),
      phase: "idle",
      transcript: [
        {
          type: "thinking",
          id: "older",
          created_at: "t1",
          text: "older reasoning",
        },
        {
          type: "thinking",
          id: "newer",
          created_at: "t2",
          text: "newer reasoning",
        },
      ],
    };
    current.session.controller.view = {
      ...applySnapshot(createSessionViewState(), thinkingSnapshot),
      connection: "live",
    };
    current.session.state = {
      kind: "attached",
      draft: current.session.draft,
      controller: current.session.controller,
    };
    current.shell.sync(current.session.state);
    current.tui.renderNow(true);

    assert.equal(handleThinkingShortcut(current.shell), true);
    assert.equal(current.shell.modals.isOpen, true);
    current.terminal.send("\r");
    assert.equal(current.shell.modals.isOpen, false);
    assert.match(
      stripTerminalSequences(current.shell.transcript.render(80).join("\n")),
      /newer reasoning/,
    );

    assert.equal(handleThinkingShortcut(current.shell, 1_000), true);
    assert.doesNotMatch(
      stripTerminalSequences(current.shell.transcript.render(80).join("\n")),
      /newer reasoning/,
    );
    assert.equal(handleThinkingShortcut(current.shell, 1_001), true);
    assert.equal(current.shell.modals.isOpen, false);
    assert.equal(current.editor.focused, true);
    current.tui.stop();
  });
});
