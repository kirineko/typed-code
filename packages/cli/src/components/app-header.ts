import {
  Text,
  type Component,
  truncateToWidth,
  visibleWidth,
} from "@earendil-works/pi-tui";

import type { AppSessionState } from "../app-session.js";
import { colors } from "../theme.js";

export class AppHeader implements Component {
  private state: AppSessionState | null = null;

  setState(state: AppSessionState): void {
    this.state = state;
  }

  invalidate(): void {}

  render(width: number): string[] {
    if (!this.state) return [""];
    const draft = this.state.draft;
    const mode =
      this.state.kind === "draft"
        ? colors.cyan("NEW")
        : this.state.kind === "creating"
          ? colors.yellow("CREATING")
          : colors.green("SESSION");
    const workspace = compactPath(draft.workspace, width < 80 ? 20 : 36);
    const model = `${draft.provider}/${draft.model}${
      draft.reasoningLevel ? ` · think ${draft.reasoningLevel}` : ""
    }`;
    const left = ` ${colors.bold("typed-code")}  ${mode}${colors.dim(` · ${workspace}`)}`;
    const right = colors.dim(model);
    const title = joinSides(left, right, width);
    return [
      ...new Text(title, 0, 0).render(width),
      colors.dim("─".repeat(Math.max(1, width))),
    ];
  }
}

function compactPath(path: string, maxWidth: number): string {
  if (path.length <= maxWidth) return path;
  const keep = Math.max(1, maxWidth - 2);
  return `…/${path.slice(-keep)}`;
}

function joinSides(left: string, right: string, width: number): string {
  const gap = width - visibleWidth(left) - visibleWidth(right);
  if (gap >= 2) return `${left}${" ".repeat(gap)}${right}`;
  const leftWidth = Math.max(1, width - visibleWidth(right) - 2);
  if (leftWidth < 12) return truncateToWidth(left, Math.max(1, width));
  return `${truncateToWidth(left, leftWidth)}  ${right}`;
}
