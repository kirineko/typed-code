import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, it } from "node:test";

import { TuiAltScreen, type Terminal } from "@earendil-works/pi-tui";
import type { EventSubscription, SessionSnapshot, TypedCodeClient } from "@typed-code/sdk";

import { ModalCoordinator } from "../src/modal-coordinator.ts";
import { configureProvider } from "../src/provider-config.ts";

class InputTerminal implements Terminal {
  columns = 80;
  rows = 24;
  readonly kittyProtocolActive = false;
  private input: ((data: string) => void) | null = null;
  start(onInput: (data: string) => void): void {
    this.input = onInput;
  }
  stop(): void {}
  async drainInput(): Promise<void> {}
  write(): void {}
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
}

function client(reload: () => Promise<void>): TypedCodeClient {
  const current: SessionSnapshot = {
    protocol_version: 1,
    session_id: "session",
    revision: 1,
    phase: "idle",
    workspace_path: "/workspace",
    provider: "cliproxy",
    model: "model",
    pending_approvals: [],
    transcript: [],
    created_at: "t",
    updated_at: "t",
    latest_event_sequence: 0,
  };
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
      await reload();
      return { reloaded: true, providers: { deepseek: "available" } };
    },
    streamEvents() {
      return subscription;
    },
  };
}

function type(terminal: InputTerminal, value: string): void {
  for (const character of value) terminal.send(character);
  terminal.send("\r");
}

describe("provider configuration", () => {
  it("masks input, writes mode 0600, and activates through reload", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-config-"));
    const file = join(root, "credentials.toml");
    const terminal = new InputTerminal();
    const tui = new TuiAltScreen(terminal);
    tui.start();
    let reloads = 0;
    try {
      const result = configureProvider({
        tui,
        modals: new ModalCoordinator(tui),
        client: client(async () => {
          reloads += 1;
        }),
        credentials: { server_token: "server-secret" },
        credentialsFile: file,
        returnFocus: null,
        provider: "deepseek",
      });
      type(terminal, "sk-provider-secret");
      const saved = await result;

      assert.equal(saved?.deepseek_api_key, "sk-provider-secret");
      assert.equal(reloads, 1);
      assert.match(await readFile(file, "utf8"), /deepseek_api_key = "sk-provider-secret"/);
      assert.equal((await stat(file)).mode & 0o777, 0o600);
    } finally {
      tui.stop();
      await rm(root, { recursive: true, force: true });
    }
  });

  it("keeps configuration open and preserves saved keys across activation retry", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-config-"));
    const file = join(root, "credentials.toml");
    const terminal = new InputTerminal();
    const tui = new TuiAltScreen(terminal);
    const modals = new ModalCoordinator(tui);
    let reloads = 0;
    tui.start();
    try {
      const result = configureProvider({
        tui,
        modals,
        client: client(async () => {
          reloads += 1;
          if (reloads === 1) throw new Error("reload rejected");
        }),
        credentials: {},
        credentialsFile: file,
        returnFocus: null,
        provider: "deepseek",
      });
      type(terminal, "sk-deepseek");
      await new Promise((resolve) => setTimeout(resolve, 0));

      assert.equal(modals.isOpen, true);
      assert.match(await readFile(file, "utf8"), /sk-deepseek/);
      terminal.send("\u001b");
      terminal.send("\u001b[B");
      terminal.send("\r");
      type(terminal, "sk-cliproxy");
      const saved = await result;

      assert.equal(saved?.deepseek_api_key, "sk-deepseek");
      assert.equal(saved?.cliproxy_api_key, "sk-cliproxy");
      assert.equal(reloads, 2);
      assert.match(await readFile(file, "utf8"), /sk-deepseek/);
      assert.match(await readFile(file, "utf8"), /sk-cliproxy/);
    } finally {
      tui.stop();
      await rm(root, { recursive: true, force: true });
    }
  });
});
