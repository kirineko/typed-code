import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { stripTerminalSequences, visibleWidth } from "@earendil-works/pi-tui";
import type { ApprovalSummary } from "@typed-code/sdk";

import { ApprovalDialog } from "../src/components/approval-dialog.ts";
import { SelectionDialog } from "../src/components/selection-dialog.ts";
import { actionOverlayOptions } from "../src/modal-coordinator.ts";

const approval: ApprovalSummary = {
  approval_id: "approval-1",
  run_id: "run-1",
  tool_name: "bash",
  summary: "bash:",
  status: "pending",
  created_at: "2026-01-01T00:00:00Z",
};

describe("ApprovalDialog", () => {
  it("approves with Enter and blocks duplicate decisions while pending", async () => {
    const pending = Promise.withResolvers<void>();
    const decisions: string[] = [];
    const dialog = new ApprovalDialog(
      approval,
      (decision) => {
        decisions.push(decision);
        return pending.promise;
      },
      () => {},
    );

    dialog.handleInput("\r");
    await Promise.resolve();
    dialog.handleInput("n");

    assert.deepEqual(decisions, ["approve"]);
    assert.match(
      stripTerminalSequences(dialog.render(52).join("\n")),
      /Approving.*waiting for the service/,
    );
    pending.resolve();
  });

  it("keeps the dialog actionable after a failed decision", async () => {
    const decisions: string[] = [];
    const dialog = new ApprovalDialog(
      approval,
      async (decision) => {
        decisions.push(decision);
        if (decisions.length === 1) throw new Error("service unavailable");
      },
      () => {},
    );

    dialog.handleInput("y");
    await new Promise((resolve) => setTimeout(resolve, 0));
    const failed = stripTerminalSequences(dialog.render(52).join("\n"));
    assert.match(failed, /Approval failed: service unavailable/);
    assert.match(failed, /Approve and continue/);

    dialog.handleInput("n");
    await Promise.resolve();
    assert.deepEqual(decisions, ["approve", "reject"]);
  });

  it("renders a filled frame without repeating the tool name", () => {
    const dialog = new ApprovalDialog(approval, async () => {}, () => {});
    const rendered = stripTerminalSequences(dialog.render(52).join("\n"));

    assert.match(rendered, /Approval required/);
    assert.match(rendered, /bash/);
    assert.doesNotMatch(rendered, /bash:\s+.*bash:/);
    assert.ok(dialog.render(52).every((line) => visibleWidth(line) === 52));
  });

  it("uses the same filled action surface for slash-command choices", () => {
    const dialog = new SelectionDialog(
      "Select model",
      "Available provider models",
      [{ value: "terra", label: "gpt-5.6-terra", description: "cliproxy" }],
    );
    const rendered = stripTerminalSequences(dialog.render(64).join("\n"));

    assert.match(rendered, /╭─+╮/);
    assert.match(rendered, /Select model/);
    assert.ok(dialog.render(64).every((line) => visibleWidth(line) === 64));
  });

  it("docks action surfaces below the header", () => {
    assert.deepEqual(actionOverlayOptions({ width: 72, maxHeight: 16 }), {
      anchor: "top-center",
      offsetY: 1,
      margin: { top: 1, right: 2, bottom: 3, left: 2 },
      width: 72,
      maxHeight: 16,
    });
  });
});
