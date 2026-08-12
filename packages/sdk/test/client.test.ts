import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { PROTOCOL_VERSION, TypedCodeError, createClient } from "../src/index.ts";

describe("createClient", () => {
  it("returns a client handle", () => {
    const client = createClient({
      baseUrl: "http://127.0.0.1:8741/",
      token: "test-token",
    });
    assert.equal(client.protocolVersion, PROTOCOL_VERSION);
    assert.equal(client.baseUrl, "http://127.0.0.1:8741");
  });

  it("rejects empty baseUrl", () => {
    assert.throws(
      () => createClient({ baseUrl: "", token: "test-token" }),
      /baseUrl is required/,
    );
  });

  it("rejects empty token", () => {
    assert.throws(
      () => createClient({ baseUrl: "http://127.0.0.1:8741", token: "" }),
      /token is required/,
    );
  });
});

describe("HTTP client", () => {
  it("parses health JSON", async () => {
    const fetchImpl: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          status: "ok",
          protocol_version: 1,
          providers: { deepseek: "available" },
          bash: { ready: true },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );

    const client = createClient({
      baseUrl: "http://test",
      token: "tok",
      fetch: fetchImpl,
    });
    const health = await client.getHealth();
    assert.equal(health.status, "ok");
    assert.equal(health.protocol_version, 1);
  });

  it("maps structured 401 errors", async () => {
    const fetchImpl: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          error: { code: "unauthorized", message: "missing or invalid bearer token" },
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      );

    const client = createClient({
      baseUrl: "http://test",
      token: "bad",
      fetch: fetchImpl,
    });
    await assert.rejects(
      () => client.listModels(),
      (err: unknown) => {
        assert.ok(err instanceof TypedCodeError);
        assert.equal(err.code, "unauthorized");
        assert.equal(err.status, 401);
        return true;
      },
    );
  });

  it("maps network failures", async () => {
    const fetchImpl: typeof fetch = async () => {
      throw new TypeError("fetch failed");
    };
    const client = createClient({
      baseUrl: "http://test",
      token: "tok",
      fetch: fetchImpl,
    });
    await assert.rejects(
      () => client.getHealth(),
      (err: unknown) => {
        assert.ok(err instanceof TypedCodeError);
        assert.equal(err.code, "network_error");
        return true;
      },
    );
  });

  it("sends bearer token on authenticated routes", async () => {
    let auth: string | null = null;
    const fetchImpl: typeof fetch = async (input, init) => {
      const headers = new Headers(init?.headers);
      auth = headers.get("Authorization");
      return new Response(JSON.stringify({ models: [] }), { status: 200 });
    };
    const client = createClient({
      baseUrl: "http://test",
      token: "secret-token",
      fetch: fetchImpl,
    });
    await client.listModels();
    assert.equal(auth, "Bearer secret-token");
  });

  it("requests authenticated service shutdown", async () => {
    let requestUrl = "";
    let requestBody = "";
    const fetchImpl: typeof fetch = async (input, init) => {
      requestUrl = String(input);
      requestBody = String(init?.body);
      return new Response(
        JSON.stringify({
          status: "stopping",
          forced: true,
          interrupted_runs: 2,
        }),
        { status: 200 },
      );
    };
    const client = createClient({
      baseUrl: "http://test",
      token: "secret-token",
      fetch: fetchImpl,
    });

    const response = await client.stopService({ force: true });

    assert.equal(requestUrl, "http://test/v1/service/stop");
    assert.deepEqual(JSON.parse(requestBody), { force: true });
    assert.equal(response.interrupted_runs, 2);
  });
});
