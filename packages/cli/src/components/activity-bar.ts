import { Text, type Component, truncateToWidth } from "@earendil-works/pi-tui";

import type { AgentActivity } from "../activity.js";
import { colors } from "../theme.js";

export class ActivityBar implements Component {
  private activity: AgentActivity = {
    kind: "ready",
    label: "Ready",
    connection: "idle",
  };
  private newOutput = false;

  setActivity(activity: AgentActivity, newOutput: boolean): void {
    this.activity = activity;
    this.newOutput = newOutput;
  }

  invalidate(): void {}

  render(width: number): string[] {
    const marker =
      this.activity.kind === "failed"
        ? colors.red("✗")
        : this.activity.kind === "ready"
          ? colors.green("●")
          : this.activity.kind === "awaiting_approval"
            ? colors.yellow("!")
            : colors.cyan("◉");
    const detail = this.activity.detail
      ? ` · ${singleLine(this.activity.detail, width < 90 ? 30 : 60)}`
      : "";
    const connection =
      this.activity.connection === "live"
        ? ""
        : ` · ${colors.yellow(this.activity.connection)}`;
    const unseen = this.newOutput ? `  ${colors.cyan("↓ new output")}` : "";
    const line = ` ${marker} ${colors.bold(this.activity.label)}${colors.dim(detail)}${connection}${unseen}`;
    return new Text(truncateToWidth(line, Math.max(1, width)), 0, 0).render(width);
  }
}

function singleLine(text: string, maxLength: number): string {
  const line = text.replace(/\s+/g, " ").trim();
  return line.length <= maxLength ? line : `${line.slice(0, maxLength - 1)}…`;
}
