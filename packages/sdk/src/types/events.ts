/** SSE / public event types aligned with contracts/events.schema.v1.json */

import type {
  ApprovalDecision,
  ApprovalSummary,
  SessionSnapshot,
  StructuredError,
  ToolCallStatus,
  TranscriptItem,
} from "./protocol.js";
import type { ProtocolVersion } from "../version.js";

export type EventType =
  | "session.snapshot"
  | "session.model_changed"
  | "run.started"
  | "run.completed"
  | "run.failed"
  | "run.cancelled"
  | "run.interrupted"
  | "message.user"
  | "message.assistant.delta"
  | "message.assistant.done"
  | "thinking.delta"
  | "thinking.done"
  | "tool.started"
  | "tool.updated"
  | "tool.completed"
  | "tool.failed"
  | "approval.requested"
  | "approval.resolved"
  | "usage.updated"
  | "context.compacted"
  | "error"
  | "replay.reset";

export const EVENT_TYPES: readonly EventType[] = [
  "session.snapshot",
  "session.model_changed",
  "run.started",
  "run.completed",
  "run.failed",
  "run.cancelled",
  "run.interrupted",
  "message.user",
  "message.assistant.delta",
  "message.assistant.done",
  "thinking.delta",
  "thinking.done",
  "tool.started",
  "tool.updated",
  "tool.completed",
  "tool.failed",
  "approval.requested",
  "approval.resolved",
  "usage.updated",
  "context.compacted",
  "error",
  "replay.reset",
] as const;

export interface EventDataBase {
  type: EventType;
}

export interface SessionSnapshotData extends EventDataBase {
  type: "session.snapshot";
  snapshot: SessionSnapshot;
}

export interface SessionModelChangedData extends EventDataBase {
  type: "session.model_changed";
  provider: "deepseek" | "cliproxy";
  model: string;
}

export interface RunStartedData extends EventDataBase {
  type: "run.started";
  run_id: string;
  prompt_preview: string;
}

export interface RunCompletedData extends EventDataBase {
  type: "run.completed";
  run_id: string;
}

export interface RunFailedData extends EventDataBase {
  type: "run.failed";
  run_id: string;
  error: StructuredError;
}

export interface RunCancelledData extends EventDataBase {
  type: "run.cancelled";
  run_id: string;
}

export interface RunInterruptedData extends EventDataBase {
  type: "run.interrupted";
  run_id: string;
}

export interface MessageUserData extends EventDataBase {
  type: "message.user";
  item: TranscriptItem;
}

export interface MessageAssistantDeltaData extends EventDataBase {
  type: "message.assistant.delta";
  message_id: string;
  delta: string;
}

export interface MessageAssistantDoneData extends EventDataBase {
  type: "message.assistant.done";
  message_id: string;
  text: string;
}

export interface ThinkingDeltaData extends EventDataBase {
  type: "thinking.delta";
  thinking_id: string;
  delta: string;
}

export interface ThinkingDoneData extends EventDataBase {
  type: "thinking.done";
  thinking_id: string;
  text: string;
}

export interface ToolStartedData extends EventDataBase {
  type: "tool.started";
  tool_call_id: string;
  tool_name: string;
  summary: string;
  status?: ToolCallStatus;
}

export interface ToolUpdatedData extends EventDataBase {
  type: "tool.updated";
  tool_call_id: string;
  summary: string;
  status: ToolCallStatus;
}

export interface ToolCompletedData extends EventDataBase {
  type: "tool.completed";
  tool_call_id: string;
  summary: string;
  ok?: boolean;
}

export interface ToolFailedData extends EventDataBase {
  type: "tool.failed";
  tool_call_id: string;
  summary: string;
}

export interface ApprovalRequestedData extends EventDataBase {
  type: "approval.requested";
  approval: ApprovalSummary;
}

export interface ApprovalResolvedData extends EventDataBase {
  type: "approval.resolved";
  approval_id: string;
  decision: ApprovalDecision;
}

export interface UsageUpdatedData extends EventDataBase {
  type: "usage.updated";
  input_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  details?: Record<string, unknown> | null;
}

export interface ContextCompactedData extends EventDataBase {
  type: "context.compacted";
  reason: string;
  removed_item_count?: number;
}

export interface ErrorEventData extends EventDataBase {
  type: "error";
  error: StructuredError;
}

export interface ReplayResetData extends EventDataBase {
  type: "replay.reset";
  reason?: string;
  snapshot: SessionSnapshot;
}

export type EventData =
  | SessionSnapshotData
  | SessionModelChangedData
  | RunStartedData
  | RunCompletedData
  | RunFailedData
  | RunCancelledData
  | RunInterruptedData
  | MessageUserData
  | MessageAssistantDeltaData
  | MessageAssistantDoneData
  | ThinkingDeltaData
  | ThinkingDoneData
  | ToolStartedData
  | ToolUpdatedData
  | ToolCompletedData
  | ToolFailedData
  | ApprovalRequestedData
  | ApprovalResolvedData
  | UsageUpdatedData
  | ContextCompactedData
  | ErrorEventData
  | ReplayResetData;

export interface EventEnvelope {
  protocol_version: ProtocolVersion;
  sequence: number;
  timestamp: string;
  session_id: string;
  run_id?: string | null;
  type: EventType;
  data: EventData;
}

export function parseEventEnvelope(raw: unknown): EventEnvelope {
  if (!raw || typeof raw !== "object") {
    throw new Error("event envelope must be an object");
  }
  const obj = raw as Record<string, unknown>;
  if (typeof obj.sequence !== "number" || typeof obj.type !== "string") {
    throw new Error("event envelope missing sequence or type");
  }
  return raw as EventEnvelope;
}
