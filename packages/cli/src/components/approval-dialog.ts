import {
  SelectList,
  matchesKey,
  type Component,
  type SelectItem,
} from "@earendil-works/pi-tui";
import type { ApprovalSummary } from "@typed-code/sdk";

import { colors, panelFrame, selectListTheme } from "../theme.js";

type ApprovalDecision = "approve" | "reject";

export class ApprovalDialog implements Component {
  private readonly approval: ApprovalSummary;
  private readonly onDecision: (decision: ApprovalDecision) => Promise<void>;
  private readonly onCancel: () => void;
  private readonly onChange: () => void;
  private readonly actions: SelectList;
  private pending: ApprovalDecision | null = null;
  private error: string | null = null;

  constructor(
    approval: ApprovalSummary,
    onDecision: (decision: ApprovalDecision) => Promise<void>,
    onCancel: () => void,
    onChange: () => void = () => {},
  ) {
    this.approval = approval;
    this.onDecision = onDecision;
    this.onCancel = onCancel;
    this.onChange = onChange;
    this.actions = new SelectList(
      [
        {
          value: "approve",
          label: "Approve and continue",
          description: "Enter or y",
        },
        {
          value: "reject",
          label: "Reject tool call",
          description: "n",
        },
        {
          value: "cancel",
          label: "Keep pending",
          description: "Esc",
        },
      ],
      3,
      selectListTheme,
    );
    this.actions.onSelect = (item) => this.select(item);
    this.actions.onCancel = this.onCancel;
  }

  invalidate(): void {
    this.actions.invalidate();
  }

  handleInput(data: string): void {
    if (this.pending) return;
    if (matchesKey(data, "y")) {
      this.decide("approve");
      return;
    }
    if (matchesKey(data, "n")) {
      this.decide("reject");
      return;
    }
    this.actions.handleInput(data);
  }

  render(width: number): string[] {
    const panelWidth = Math.max(20, width);
    const innerWidth = Math.max(1, panelWidth - 4);
    const body = [
      colors.yellow(colors.bold("Approval required")),
      colors.bold(this.approval.tool_name),
      colors.dim(cleanSummary(this.approval.tool_name, this.approval.summary)),
    ];

    if (this.pending) {
      body.push(
        "",
        colors.yellow(
          this.pending === "approve"
            ? "Approving… waiting for the service"
            : "Rejecting… waiting for the service",
        ),
      );
    } else {
      if (this.error) body.push("", colors.red(this.error));
      body.push("", ...this.actions.render(innerWidth));
    }

    return panelFrame(body, panelWidth);
  }

  private select(item: SelectItem): void {
    if (item.value === "cancel") {
      this.onCancel();
      return;
    }
    this.decide(item.value as ApprovalDecision);
  }

  private decide(decision: ApprovalDecision): void {
    if (this.pending) return;
    this.pending = decision;
    this.error = null;
    this.onChange();
    void Promise.resolve()
      .then(() => this.onDecision(decision))
      .catch((error: unknown) => {
        this.pending = null;
        this.error = `Approval failed: ${error instanceof Error ? error.message : String(error)}`;
        this.onChange();
      });
  }
}

function cleanSummary(toolName: string, summary: string): string {
  const clean = summary.trim();
  const normalized = clean.replace(/:$/, "").trim().toLowerCase();
  return normalized === toolName.trim().toLowerCase() ? "No additional details" : clean;
}

