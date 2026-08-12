import type { ConnectionState, SessionViewState } from "@typed-code/sdk";


export type AgentActivityKind =
  | "ready"
  | "creating"
  | "preparing"
  | "thinking"
  | "calling_tool"
  | "awaiting_approval"
  | "responding"
  | "finalizing"
  | "cancelling"
  | "failed";

export interface AgentActivity {
  kind: AgentActivityKind;
  label: string;
  detail?: string;
  connection: ConnectionState;
}

export type ActivitySource =
  | { kind: "draft" }
  | { kind: "creating" }
  | { kind: "attached"; view: SessionViewState };

export function deriveAgentActivity(
  state: ActivitySource,
  options: { cancelling?: boolean } = {},
): AgentActivity {
  const view = state.kind === "attached" ? state.view : null;
  const connection = view?.connection ?? "idle";

  if (options.cancelling) {
    return { kind: "cancelling", label: "Cancelling", connection };
  }
  if (state.kind === "creating") {
    return { kind: "creating", label: "Creating session", connection };
  }
  if (!view) {
    return { kind: "ready", label: "Ready", detail: "new session", connection };
  }

  const approval = view.snapshot?.pending_approvals[0];
  if (approval) {
    return {
      kind: "awaiting_approval",
      label: "Awaiting approval",
      detail: toolDetail(approval.tool_name, approval.summary, true),
      connection,
    };
  }

  const activeTool = Object.values(view.tools).find(
    (tool) => tool.status === "started" || tool.status === "running",
  );
  if (activeTool) {
    const detail = toolDetail(activeTool.tool_name, activeTool.summary, false);
    return {
      kind: "calling_tool",
      label: `Calling ${activeTool.tool_name}`,
      ...(detail ? { detail } : {}),
      connection,
    };
  }

  const thinking = latestBuffer(view.thinkingBuffers);
  if (thinking) {
    return {
      kind: "thinking",
      label: "Thinking",
      detail: thinking,
      connection,
    };
  }

  const response = latestBuffer(view.assistantBuffers);
  if (response) {
    return {
      kind: "responding",
      label: "Responding",
      detail: response,
      connection,
    };
  }

  if (view.error) {
    return {
      kind: "failed",
      label: "Failed",
      detail: view.error.message,
      connection,
    };
  }
  if (
    view.phase === "running" &&
    (view.lastEvent?.data.type === "message.assistant.done" ||
      view.lastEvent?.data.type === "usage.updated")
  ) {
    return { kind: "finalizing", label: "Finalizing", connection };
  }

  if (view.phase === "running") {
    return { kind: "preparing", label: "Preparing", connection };
  }
  return { kind: "ready", label: "Ready", connection };
}

function latestBuffer(buffers: Record<string, string>): string | undefined {
  const entries = Object.entries(buffers);
  const last = entries[entries.length - 1];
  if (!last) {
    return undefined;
  }
  const text = last[1].trim();
  return text || undefined;
}

function toolDetail(
  toolName: string,
  summary: string,
  includeName: true,
): string;
function toolDetail(
  toolName: string,
  summary: string,
  includeName: false,
): string | undefined;
function toolDetail(
  toolName: string,
  summary: string,
  includeName: boolean,
): string | undefined {
  const clean = summary.trim();
  const duplicate =
    clean.replace(/:$/, "").trim().toLowerCase() === toolName.trim().toLowerCase();
  if (duplicate || !clean) return includeName ? toolName : undefined;
  return includeName ? `${toolName} · ${clean}` : clean;
}
