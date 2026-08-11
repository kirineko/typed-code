import type { EventEnvelope } from "../types/events.js";
import type {
  ApprovalSummary,
  SessionSnapshot,
  TranscriptItem,
} from "../types/protocol.js";
import {
  initialSessionViewState,
  type SessionViewState,
  type StreamingTool,
} from "./types.js";

export function applySnapshot(
  state: SessionViewState,
  snapshot: SessionSnapshot,
): SessionViewState {
  return {
    ...state,
    snapshot,
    phase: snapshot.phase,
    lastSequence: Math.max(state.lastSequence, snapshot.latest_event_sequence),
    connection: state.connection === "idle" ? "live" : state.connection,
    error: null,
    // Snapshot is authoritative for transcript; clear ephemeral buffers
    assistantBuffers: {},
    thinkingBuffers: {},
  };
}

export function applyEvent(
  state: SessionViewState,
  event: EventEnvelope,
): SessionViewState {
  if (event.sequence <= state.lastSequence) {
    return state;
  }

  let next: SessionViewState = {
    ...state,
    lastSequence: event.sequence,
    lastEvent: event,
    connection: "live",
  };

  const data = event.data;
  switch (data.type) {
    case "run.started": {
      next = patchSnapshot(next, (s) => ({
        ...s,
        phase: "running",
        active_run: {
          run_id: data.run_id,
          status: "running",
          prompt_preview: data.prompt_preview,
          started_at: event.timestamp,
          ended_at: null,
        },
      }));
      next = { ...next, phase: "running" };
      break;
    }
    case "run.completed":
    case "run.failed":
    case "run.cancelled":
    case "run.interrupted": {
      next = patchSnapshot(next, (s) => ({
        ...s,
        phase: "idle",
        active_run: null,
        pending_approvals: [],
      }));
      next = { ...next, phase: "idle" };
      if (data.type === "run.failed") {
        next = { ...next, error: data.error };
      }
      break;
    }
    case "message.user": {
      next = appendTranscript(next, data.item);
      break;
    }
    case "message.assistant.delta": {
      const buffers = { ...next.assistantBuffers };
      buffers[data.message_id] = (buffers[data.message_id] ?? "") + data.delta;
      next = { ...next, assistantBuffers: buffers };
      break;
    }
    case "message.assistant.done": {
      const buffers = { ...next.assistantBuffers };
      delete buffers[data.message_id];
      next = {
        ...appendTranscript(next, {
          type: "assistant_message",
          id: data.message_id,
          created_at: event.timestamp,
          text: data.text,
        }),
        assistantBuffers: buffers,
      };
      break;
    }
    case "thinking.delta": {
      const buffers = { ...next.thinkingBuffers };
      buffers[data.thinking_id] = (buffers[data.thinking_id] ?? "") + data.delta;
      next = { ...next, thinkingBuffers: buffers };
      break;
    }
    case "thinking.done": {
      const buffers = { ...next.thinkingBuffers };
      delete buffers[data.thinking_id];
      next = {
        ...appendTranscript(next, {
          type: "thinking",
          id: data.thinking_id,
          created_at: event.timestamp,
          text: data.text,
        }),
        thinkingBuffers: buffers,
      };
      break;
    }
    case "tool.started":
    case "tool.updated": {
      const tools = { ...next.tools };
      const prev = tools[data.tool_call_id];
      const tool: StreamingTool = {
        tool_call_id: data.tool_call_id,
        tool_name:
          data.type === "tool.started"
            ? data.tool_name
            : (prev?.tool_name ?? "tool"),
        summary: data.summary,
        status: data.status ?? (data.type === "tool.started" ? "started" : "running"),
      };
      tools[data.tool_call_id] = tool;
      next = { ...next, tools };
      break;
    }
    case "tool.completed":
    case "tool.failed": {
      const tools = { ...next.tools };
      const prev = tools[data.tool_call_id];
      tools[data.tool_call_id] = {
        tool_call_id: data.tool_call_id,
        tool_name: prev?.tool_name ?? "tool",
        summary: data.summary,
        status: data.type === "tool.completed" ? "completed" : "failed",
      };
      next = { ...next, tools };
      break;
    }
    case "approval.requested": {
      next = patchSnapshot(next, (s) => ({
        ...s,
        phase: "awaiting_approval",
        pending_approvals: upsertApproval(s.pending_approvals, data.approval),
      }));
      next = { ...next, phase: "awaiting_approval" };
      break;
    }
    case "approval.resolved": {
      next = patchSnapshot(next, (s) => ({
        ...s,
        pending_approvals: s.pending_approvals.filter(
          (a) => a.approval_id !== data.approval_id,
        ),
        phase:
          s.pending_approvals.filter((a) => a.approval_id !== data.approval_id)
            .length === 0
            ? "running"
            : "awaiting_approval",
      }));
      if (next.snapshot) {
        next = { ...next, phase: next.snapshot.phase };
      }
      break;
    }
    case "usage.updated": {
      const lastUsage: SessionViewState["lastUsage"] = {};
      if (data.input_tokens !== undefined) {
        lastUsage.input_tokens = data.input_tokens;
      }
      if (data.output_tokens !== undefined) {
        lastUsage.output_tokens = data.output_tokens;
      }
      if (data.total_tokens !== undefined) {
        lastUsage.total_tokens = data.total_tokens;
      }
      next = { ...next, lastUsage };
      break;
    }
    case "error": {
      next = { ...next, error: data.error };
      break;
    }
    case "session.snapshot": {
      next = applySnapshot(next, data.snapshot);
      break;
    }
    case "session.model_changed": {
      next = patchSnapshot(next, (s) => ({
        ...s,
        provider: data.provider,
        model: data.model,
      }));
      break;
    }
    case "replay.reset": {
      // Prefer stream controller handling; still apply snapshot if seen here.
      next = applySnapshot(next, data.snapshot);
      break;
    }
    case "context.compacted":
    default:
      break;
  }

  return next;
}

export function createSessionViewState(): SessionViewState {
  return initialSessionViewState();
}

function patchSnapshot(
  state: SessionViewState,
  fn: (s: SessionSnapshot) => SessionSnapshot,
): SessionViewState {
  if (!state.snapshot) {
    return state;
  }
  return { ...state, snapshot: fn(state.snapshot) };
}

function appendTranscript(
  state: SessionViewState,
  item: TranscriptItem,
): SessionViewState {
  return patchSnapshot(state, (s) => {
    if (s.transcript.some((t) => t.id === item.id)) {
      return s;
    }
    return { ...s, transcript: [...s.transcript, item] };
  });
}

function upsertApproval(
  list: ApprovalSummary[],
  approval: ApprovalSummary,
): ApprovalSummary[] {
  const idx = list.findIndex((a) => a.approval_id === approval.approval_id);
  if (idx === -1) {
    return [...list, approval];
  }
  const copy = list.slice();
  copy[idx] = approval;
  return copy;
}
