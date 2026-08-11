/** Protocol v1 types aligned with server contracts (hand-authored for MVP). */

import type { ProtocolVersion } from "../version.js";

export type SessionPhase = "idle" | "running" | "awaiting_approval";

export type RunStatus =
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

export type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled";

export type ApprovalDecision = "approve" | "reject";

export type ProviderName = "deepseek" | "cliproxy";

export type ProviderAvailability = "available" | "missing_credentials";

export type ErrorCode =
  | "validation_error"
  | "protocol_version_error"
  | "unauthorized"
  | "not_found"
  | "conflict"
  | "missing_credentials"
  | "model_selection_error"
  | "internal_error"
  | "run_failed"
  | "configuration_error"
  | "network_error"
  | "protocol_mismatch";

export type TranscriptItemType =
  | "user_message"
  | "assistant_message"
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "system_notice";

export type ToolCallStatus =
  | "started"
  | "running"
  | "completed"
  | "failed"
  | "denied";

export interface StructuredError {
  code: ErrorCode | string;
  message: string;
  details?: Record<string, unknown> | null;
}

export interface ErrorResponse {
  error: StructuredError;
}

export interface ModelCapabilities {
  text_input: boolean;
  text_output: boolean;
  image_input: boolean;
  tools: boolean;
  parallel_tool_calls: boolean;
  reasoning_levels: string[];
}

export interface ModelInfo {
  provider: ProviderName;
  model_id: string;
  display_name?: string | null;
  availability: ProviderAvailability;
  capabilities?: ModelCapabilities;
  context_token_budget?: number;
}

export interface UpdateSessionModelRequest {
  provider: ProviderName;
  model: string;
}

export interface ConfigReloadResponse {
  reloaded: boolean;
  providers: Record<string, string>;
}

export interface ModelListResponse {
  models: ModelInfo[];
}

export interface CreateSessionRequest {
  workspace_path: string;
  provider?: ProviderName | null;
  model?: string | null;
}

export interface CreateTurnRequest {
  prompt: string;
}

export interface ApprovalDecisionRequest {
  decision: ApprovalDecision;
}

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  prompt_preview: string;
  started_at: string;
  ended_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface ApprovalSummary {
  approval_id: string;
  run_id: string;
  tool_name: string;
  summary: string;
  status: ApprovalStatus;
  created_at: string;
}

export interface TranscriptItemBase {
  id: string;
  created_at: string;
}

export interface UserMessageItem extends TranscriptItemBase {
  type: "user_message";
  text: string;
}

export interface AssistantMessageItem extends TranscriptItemBase {
  type: "assistant_message";
  text: string;
}

export interface ThinkingItem extends TranscriptItemBase {
  type: "thinking";
  text: string;
}

export interface ToolCallItem extends TranscriptItemBase {
  type: "tool_call";
  tool_name: string;
  summary: string;
  status: ToolCallStatus;
  args_preview?: string | null;
}

export interface ToolResultItem extends TranscriptItemBase {
  type: "tool_result";
  tool_call_id: string;
  ok: boolean;
  summary: string;
  truncated?: boolean;
}

export interface SystemNoticeItem extends TranscriptItemBase {
  type: "system_notice";
  text: string;
  kind?: string | null;
}

export type TranscriptItem =
  | UserMessageItem
  | AssistantMessageItem
  | ThinkingItem
  | ToolCallItem
  | ToolResultItem
  | SystemNoticeItem;

export interface SessionSummary {
  session_id: string;
  revision: number;
  phase: SessionPhase;
  workspace_path: string;
  provider: ProviderName;
  model: string;
  created_at: string;
  updated_at: string;
  active_run_id?: string | null;
}

export interface SessionSnapshot {
  protocol_version: ProtocolVersion;
  session_id: string;
  revision: number;
  phase: SessionPhase;
  workspace_path: string;
  provider: ProviderName;
  model: string;
  active_run?: RunSummary | null;
  pending_approvals: ApprovalSummary[];
  transcript: TranscriptItem[];
  created_at: string;
  updated_at: string;
  latest_event_sequence: number;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

export interface CreateSessionResponse {
  snapshot: SessionSnapshot;
}

export interface CreateTurnResponse {
  run_id: string;
  revision: number;
  phase: SessionPhase;
  status: "accepted";
}

export interface HealthResponse {
  status: string;
  protocol_version: number;
  providers: Record<string, string>;
  bash: { ready: boolean; executable?: string | null };
  default_provider?: string;
  default_model?: string;
}

/** Paths the SDK documents (must match contracts/openapi.v1.json). */
export const SDK_HTTP_PATHS = [
  "/v1/health",
  "/v1/models",
  "/v1/config/reload",
  "/v1/sessions",
  "/v1/sessions/{session_id}",
  "/v1/sessions/{session_id}/model",
  "/v1/sessions/{session_id}/turns",
  "/v1/sessions/{session_id}/abort",
  "/v1/sessions/{session_id}/approvals/{approval_id}",
  "/v1/sessions/{session_id}/events",
] as const;
