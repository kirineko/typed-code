import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { actionFromKeyData } from "../src/index.ts";

describe("keybindings", () => {
  it("maps ctrl+c to quit", () => {
    assert.equal(
      actionFromKeyData("\u0003", { approvalPending: false, runActive: false }).type,
      "quit",
    );
  });

  it("maps esc to abort when run active", () => {
    assert.equal(
      actionFromKeyData("\u001b", { approvalPending: false, runActive: true }).type,
      "abort",
    );
    assert.equal(
      actionFromKeyData("\u001b", { approvalPending: false, runActive: false }).type,
      "none",
    );
  });

  it("maps y/n when approval pending", () => {
    assert.equal(
      actionFromKeyData("y", { approvalPending: true, runActive: true }).type,
      "approve",
    );
    assert.equal(
      actionFromKeyData("n", { approvalPending: true, runActive: true }).type,
      "reject",
    );
    assert.equal(
      actionFromKeyData("y", { approvalPending: false, runActive: true }).type,
      "none",
    );
  });
});
