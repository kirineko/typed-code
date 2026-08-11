import {
  Text,
  type Component,
  truncateToWidth,
  visibleWidth,
} from "@earendil-works/pi-tui";

import type { AppSessionState } from "../app-session.js";
import { colors } from "../theme.js";

export class StatusFooter implements Component {
  private state: AppSessionState | null = null;

  setState(state: AppSessionState): void {
    this.state = state;
  }

  invalidate(): void {}

  render(width: number): string[] {
    if (!this.state) return [""];
    const draft = this.state.draft;
    const view = this.state.kind === "attached" ? this.state.controller.view : null;
    const connection = view?.connection ?? "draft";
    const usage = view?.lastUsage;
    const budget = view?.contextBudget ?? draft.contextBudget;
    const total = usage?.total_tokens ?? null;
    const usageText = formatUsage(total, budget);
    const io =
      width >= 96 && usage
        ? ` · in ${formatTokenCount(usage.input_tokens)} · out ${formatTokenCount(usage.output_tokens)}`
        : "";
    const pending = view?.phase === "running" ? " · usage pending" : "";
    const keys = width >= 72 ? "   /help · Ctrl+C quit" : "   /help";
    const connectionText =
      connection === "live" ? colors.green("live") : colors.yellow(connection);
    const left = ` ${connectionText} · ${usageText}${io}${pending}`;
    const available = Math.max(1, width - keys.length);
    const clippedLeft = truncateToWidth(left, available);
    const line = `${clippedLeft}${" ".repeat(
      Math.max(0, width - visibleWidth(clippedLeft) - keys.length),
    )}${keys}`;
    return new Text(colors.dim(truncateToWidth(line, Math.max(1, width))), 0, 0).render(width);
  }
}

export function formatTokenCount(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value < 1_000) return String(value);
  if (value < 1_000_000) {
    const digits = value < 10_000 ? 1 : 0;
    return `${(value / 1_000).toFixed(digits)}k`;
  }
  return `${(value / 1_000_000).toFixed(1)}m`;
}

function formatUsage(total: number | null, budget: number | null): string {
  if (budget == null || budget <= 0) {
    return `ctx ${formatTokenCount(total)}/—`;
  }
  if (total == null) {
    return `ctx —/${formatTokenCount(budget)}`;
  }
  const percent = Math.min(999, (total / budget) * 100);
  return `ctx ${formatTokenCount(total)}/${formatTokenCount(budget)} · ${percent.toFixed(1)}%`;
}
