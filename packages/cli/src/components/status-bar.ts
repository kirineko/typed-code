import { Text, type Component } from "@earendil-works/pi-tui";
import type { SessionViewState } from "@typed-code/sdk";

import { formatApprovalHint, formatStatusLine } from "../render/format.js";
import { colors } from "../theme.js";

export class StatusBar implements Component {
  private line = new Text("");
  private approval = new Text("");
  private helpVisible = false;
  private notice = "";

  setView(view: SessionViewState, notice?: string): void {
    if (notice !== undefined) {
      this.notice = notice;
    }
    const status = formatStatusLine(view);
    const extra = this.notice ? `  · ${this.notice}` : "";
    this.line.setText(colors.dim(status + extra));
    const hint = formatApprovalHint(view);
    this.approval.setText(hint ? colors.yellow(hint) : "");
  }

  toggleHelp(): void {
    this.helpVisible = !this.helpVisible;
  }

  setNotice(notice: string): void {
    this.notice = notice;
  }

  invalidate(): void {
    this.line.invalidate();
    this.approval.invalidate();
  }

  render(width: number): string[] {
    const lines = [...this.line.render(width)];
    const approvalLines = this.approval.render(width);
    if (approvalLines.some((l) => l.trim().length > 0)) {
      lines.push(...approvalLines);
    }
    if (this.helpVisible) {
      lines.push(
        ...new Text(
          colors.dim(
            "keys: Enter=submit  Esc/Ctrl+D=abort  y/n=approval  Ctrl+C=quit  ?=help",
          ),
        ).render(width),
      );
    }
    return lines;
  }
}
