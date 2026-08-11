import assert from "node:assert/strict";
import { mkdtemp, realpath, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, it } from "node:test";

import type { SessionSummary } from "@typed-code/sdk";

import {
  groupSessionsByWorkspace,
  normalizeWorkspace,
  sessionsForWorkspace,
} from "../src/workspace-sessions.ts";

function session(
  sessionId: string,
  workspacePath: string,
  updatedAt: string,
): SessionSummary {
  return {
    session_id: sessionId,
    revision: 1,
    phase: "idle",
    workspace_path: workspacePath,
    provider: "cliproxy",
    model: "m",
    created_at: updatedAt,
    updated_at: updatedAt,
    active_run_id: null,
  };
}

describe("workspace session organization", () => {
  it("normalizes symlinked workspaces to a canonical directory", async () => {
    const root = await mkdtemp(join(tmpdir(), "typed-code-workspace-"));
    const link = `${root}-link`;
    await symlink(root, link);
    try {
      const identity = await normalizeWorkspace(link);
      assert.equal(identity.canonicalPath, await realpath(root));
    } finally {
      await rm(link, { force: true });
      await rm(root, { force: true, recursive: true });
    }
  });

  it("filters and deterministically sorts current-project sessions", () => {
    const sessions = [
      session("b", "/project", "2026-01-02T00:00:00Z"),
      session("c", "/other", "2026-01-03T00:00:00Z"),
      session("a", "/project", "2026-01-02T00:00:00Z"),
    ];

    assert.deepEqual(
      sessionsForWorkspace(sessions, "/project").map((item) => item.session_id),
      ["a", "b"],
    );
  });

  it("groups workspaces and disambiguates equal basenames", () => {
    const groups = groupSessionsByWorkspace([
      session("new", "/home/a/app", "2026-02-02T00:00:00Z"),
      session("old", "/home/a/app", "2026-01-01T00:00:00Z"),
      session("other", "/home/b/app", "2026-01-03T00:00:00Z"),
    ]);

    assert.deepEqual(
      groups.map((group) => group.label),
      ["app — /home/a", "app — /home/b"],
    );
    assert.deepEqual(
      groups[0]?.sessions.map((item) => item.session_id),
      ["new", "old"],
    );
  });
});
