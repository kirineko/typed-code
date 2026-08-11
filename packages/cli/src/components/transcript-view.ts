import { Text, type Component } from "@earendil-works/pi-tui";
import type { SessionViewState } from "@typed-code/sdk";

import {
  formatToolLine,
  formatTranscriptItem,
} from "../render/format.js";
import { colors } from "../theme.js";

/** Rebuildable transcript list (MVP). */
export class TranscriptView implements Component {
  private lines: Component[] = [];

  setView(view: SessionViewState): void {
    const next: Component[] = [];
    const snap = view.snapshot;
    if (snap) {
      for (const item of snap.transcript) {
        const text = formatTranscriptItem(item);
        if (item.type === "user_message") {
          next.push(new Text(colors.cyan(text)));
        } else if (item.type === "thinking" || item.type === "system_notice") {
          next.push(new Text(colors.dim(text)));
        } else if (item.type === "tool_call" || item.type === "tool_result") {
          next.push(new Text(colors.yellow(text)));
        } else {
          next.push(new Text(text));
        }
      }
    }
    for (const [id, buf] of Object.entries(view.assistantBuffers)) {
      next.push(new Text(colors.green(`assistant… (${id.slice(0, 6)}): ${buf}`)));
    }
    for (const [id, buf] of Object.entries(view.thinkingBuffers)) {
      next.push(new Text(colors.dim(`thinking… (${id.slice(0, 6)}): ${buf}`)));
    }
    for (const tool of Object.values(view.tools)) {
      if (tool.status === "completed" || tool.status === "failed") {
        // Prefer transcript tool_result when present; still show active tools
        continue;
      }
      next.push(new Text(colors.yellow(formatToolLine(tool))));
    }
    if (view.error) {
      next.push(new Text(colors.red(`error[${view.error.code}]: ${view.error.message}`)));
    }
    if (next.length === 0) {
      next.push(new Text(colors.dim("(empty transcript — type a prompt below)")));
    }
    this.lines = next;
  }

  invalidate(): void {
    for (const c of this.lines) {
      c.invalidate();
    }
  }

  render(width: number): string[] {
    const out: string[] = [];
    for (const c of this.lines) {
      out.push(...c.render(width));
    }
    return out;
  }
}
