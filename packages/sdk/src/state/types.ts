import type { EventEnvelope } from "../types/events.js";
import type {
  SessionPhase,
  SessionSnapshot,
  StructuredError,
  ToolCallStatus,
} from "../types/protocol.js";

export type ConnectionState = "idle" | "live" | "reconnecting" | "error";

export interface StreamingTool {
  tool_call_id: string;
  tool_name: string;
  summary: string;
  status: ToolCallStatus;
}

export interface SessionViewState {
  snapshot: SessionSnapshot | null;
  phase: SessionPhase | "disconnected" | "connecting";
  lastSequence: number;
  connection: ConnectionState;
  /** In-flight assistant text keyed by message id */
  assistantBuffers: Record<string, string>;
  /** In-flight thinking text keyed by thinking id */
  thinkingBuffers: Record<string, string>;
  tools: Record<string, StreamingTool>;
  lastUsage: {
    input_tokens?: number | null;
    output_tokens?: number | null;
    total_tokens?: number | null;
  } | null;
  /** Context token budget for the selected model (CLI/status display). */
  contextBudget: number | null;
  error: StructuredError | null;
  lastEvent: EventEnvelope | null;
}

export function initialSessionViewState(): SessionViewState {
  return {
    snapshot: null,
    phase: "disconnected",
    lastSequence: 0,
    connection: "idle",
    assistantBuffers: {},
    thinkingBuffers: {},
    tools: {},
    lastUsage: null,
    contextBudget: null,
    error: null,
    lastEvent: null,
  };
}
