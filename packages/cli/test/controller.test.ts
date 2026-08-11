import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type {
  CreateSessionResponse,
  CreateTurnResponse,
  EventSubscription,
  SessionSnapshot,
  StreamOptions,
  TypedCodeClient,
} from "@typed-code/sdk";

import { SessionController } from "../src/index.ts";

function snapshot(partial: Partial<SessionSnapshot> = {}): SessionSnapshot {
  return {
    protocol_version: 1,
    session_id: "sess-1",
    revision: 1,
    phase: "idle",
    workspace_path: "/ws",
    provider: "cliproxy",
    model: "m1",
    pending_approvals: [],
    transcript: [
      {
        type: "user_message",
        id: "u1",
        created_at: "t",
        text: "hi",
      },
    ],
    created_at: "t",
    updated_at: "t",
    latest_event_sequence: 2,
    ...partial,
  };
}

function mockClient(overrides: Partial<TypedCodeClient> = {}): TypedCodeClient {
  let closed = false;
  const sub: EventSubscription = {
    get lastSequence() {
      return 2;
    },
    close() {
      closed = true;
    },
  };
  return {
    protocolVersion: 1,
    baseUrl: "http://test",
    getHealth: async () => ({
      status: "ok",
      protocol_version: 1,
      providers: {},
      bash: { ready: true },
    }),
    listModels: async () => ({ models: [] }),
    listSessions: async () => ({ sessions: [] }),
    createSession: async () =>
      ({ snapshot: snapshot() }) satisfies CreateSessionResponse,
    getSession: async () => snapshot(),
    createTurn: async () =>
      ({
        run_id: "r1",
        revision: 2,
        phase: "running",
        status: "accepted",
      }) satisfies CreateTurnResponse,
    abort: async () => snapshot({ phase: "idle" }),
    decideApproval: async () => snapshot({ phase: "running", pending_approvals: [] }),
    streamEvents: (_id: string, _opts: StreamOptions) => sub,
    ...overrides,
    // expose for assertions
    _closed: () => closed,
  } as TypedCodeClient & { _closed: () => boolean };
}

describe("SessionController", () => {
  it("attaches and disposes stream without abort", async () => {
    const client = mockClient();
    const c = new SessionController(client);
    await c.attach("sess-1");
    assert.equal(c.sessionId, "sess-1");
    assert.equal(c.view.phase, "idle");
    c.dispose();
    assert.equal((client as { _closed: () => boolean })._closed(), true);
  });

  it("rejects submit when not idle", async () => {
    const client = mockClient({
      getSession: async () => snapshot({ phase: "running" }),
    });
    const c = new SessionController(client);
    await c.attach("sess-1");
    await assert.rejects(() => c.submit("hello"), /cannot submit/);
  });

  it("submits when idle", async () => {
    let turned = false;
    const client = mockClient({
      createTurn: async () => {
        turned = true;
        return {
          run_id: "r1",
          revision: 2,
          phase: "running",
          status: "accepted",
        };
      },
      getSession: async () =>
        turned ? snapshot({ phase: "idle", revision: 3 }) : snapshot(),
    });
    const c = new SessionController(client);
    await c.attach("sess-1");
    await c.submit("hello");
    assert.equal(turned, true);
  });

  it("approve uses pending approval id", async () => {
    let seenId: string | null = null;
    const client = mockClient({
      getSession: async () =>
        snapshot({
          phase: "awaiting_approval",
          pending_approvals: [
            {
              approval_id: "appr-99",
              run_id: "r1",
              tool_name: "write_file",
              summary: "write x",
              status: "pending",
              created_at: "t",
            },
          ],
        }),
      decideApproval: async (_s, id) => {
        seenId = id;
        return snapshot({ phase: "idle", pending_approvals: [] });
      },
    });
    const c = new SessionController(client);
    await c.attach("sess-1");
    await c.approve();
    assert.equal(seenId, "appr-99");
  });
});
