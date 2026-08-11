/**
 * Transport-neutral typed-code client SDK.
 *
 * Must not import `@earendil-works/pi-tui` or embed agent runtime behavior.
 */

export { createClient, type ClientOptions, type TypedCodeClient } from "./http/client.js";
export { TypedCodeError } from "./http/errors.js";
export { SseParser, type SseFrame } from "./sse/parse.js";
export {
  streamSessionEvents,
  type EventSubscription,
  type StreamOptions,
} from "./sse/stream.js";
export {
  applyEvent,
  applySnapshot,
  createSessionViewState,
} from "./state/reducer.js";
export {
  initialSessionViewState,
  type ConnectionState,
  type SessionViewState,
  type StreamingTool,
} from "./state/types.js";
export {
  EVENT_TYPES,
  parseEventEnvelope,
  type EventData,
  type EventEnvelope,
  type EventType,
} from "./types/events.js";
export {
  SDK_HTTP_PATHS,
  type ApprovalDecision,
  type ApprovalDecisionRequest,
  type ApprovalStatus,
  type ApprovalSummary,
  type CreateSessionRequest,
  type CreateSessionResponse,
  type CreateTurnRequest,
  type CreateTurnResponse,
  type ErrorCode,
  type ErrorResponse,
  type HealthResponse,
  type ModelInfo,
  type ModelListResponse,
  type ProviderAvailability,
  type ProviderName,
  type ReasoningLevel,
  type RunStatus,
  type RunSummary,
  type SessionListResponse,
  type SessionPhase,
  type SessionSnapshot,
  type SessionSummary,
  type StructuredError,
  type TranscriptItem,
  type TranscriptItemType,
  type ToolCallStatus,
} from "./types/protocol.js";
export { PROTOCOL_VERSION, type ProtocolVersion } from "./version.js";
