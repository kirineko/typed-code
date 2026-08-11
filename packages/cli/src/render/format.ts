/** Pure formatting helpers for transcript / status (no TUI). */

import type {
  SessionViewState,
  StreamingTool,
  TranscriptItem,
} from "@typed-code/sdk";

export function formatStatusLine(view: SessionViewState): string {
  const snap = view.snapshot;
  const model = snap ? `${snap.provider}/${snap.model}` : "—";
  const phase = view.phase;
  const conn = view.connection;
  const seq = view.lastSequence;
  const pending = snap?.pending_approvals.length ?? 0;
  const parts = [
    "typed-code",
    `model=${model}`,
    `phase=${phase}`,
    `conn=${conn}`,
    `seq=${seq}`,
  ];
  if (pending > 0) {
    parts.push(`approvals=${pending}`);
  }
  if (view.lastUsage?.total_tokens != null) {
    const used = view.lastUsage.total_tokens;
    const budget = view.contextBudget;
    if (budget != null && budget > 0) {
      parts.push(`tokens≈${used}/${budget}`);
    } else {
      parts.push(`tokens≈${used}`);
    }
  }
  return parts.join("  ");
}

export function formatTranscriptItem(item: TranscriptItem): string {
  switch (item.type) {
    case "user_message":
      return `you: ${item.text}`;
    case "assistant_message":
      return `assistant: ${item.text}`;
    case "thinking":
      return `thinking: ${item.text}`;
    case "tool_call":
      return `tool ${item.tool_name} [${item.status}]: ${item.summary}`;
    case "tool_result":
      return `tool-result ${item.ok ? "ok" : "err"}: ${item.summary}`;
    case "system_notice":
      return `notice: ${item.text}`;
    default:
      return JSON.stringify(item);
  }
}

export function formatToolLine(tool: StreamingTool): string {
  return `tool ${tool.tool_name} [${tool.status}]: ${tool.summary}`;
}

export function formatApprovalHint(view: SessionViewState): string | null {
  const pending = view.snapshot?.pending_approvals[0];
  if (!pending) {
    return null;
  }
  return `approval pending [${pending.approval_id.slice(0, 8)}…] ${pending.tool_name}: ${pending.summary}  (y=approve n=reject)`;
}

export function formatConnectionError(err: unknown): string {
  if (err && typeof err === "object" && "message" in err) {
    return `connection: ${String((err as { message: unknown }).message)}`;
  }
  return `connection: ${String(err)}`;
}

export function canSubmit(view: SessionViewState): boolean {
  return view.phase === "idle" && view.connection !== "error";
}

export function isRunActive(view: SessionViewState): boolean {
  return view.phase === "running" || view.phase === "awaiting_approval";
}
