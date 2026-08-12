import { streamSessionEvents, type EventSubscription, type StreamOptions } from "../sse/stream.js";
import type {
  ApprovalDecisionRequest,
  ConfigReloadResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  CreateTurnRequest,
  CreateTurnResponse,
  HealthResponse,
  ModelListResponse,
  SessionListResponse,
  SessionSnapshot,
  ServiceStopRequest,
  ServiceStopResponse,
  UpdateSessionModelRequest,
} from "../types/protocol.js";
import { PROTOCOL_VERSION, type ProtocolVersion } from "../version.js";
import { apiRequest, readJson, type FetchLike } from "./fetch.js";

export interface ClientOptions {
  /** Base URL of the typed-code service, e.g. `http://127.0.0.1:8741`. */
  baseUrl: string;
  /** Bearer token matching the service `server_token`. */
  token: string;
  /** Injectable fetch (defaults to global fetch). */
  fetch?: FetchLike;
  protocolVersion?: ProtocolVersion;
}

export interface TypedCodeClient {
  readonly protocolVersion: ProtocolVersion;
  readonly baseUrl: string;
  getHealth(): Promise<HealthResponse>;
  listModels(opts?: { refresh?: boolean }): Promise<ModelListResponse>;
  listSessions(): Promise<SessionListResponse>;
  createSession(body: CreateSessionRequest): Promise<CreateSessionResponse>;
  getSession(sessionId: string): Promise<SessionSnapshot>;
  createTurn(
    sessionId: string,
    body: CreateTurnRequest,
  ): Promise<CreateTurnResponse>;
  abort(sessionId: string): Promise<SessionSnapshot>;
  decideApproval(
    sessionId: string,
    approvalId: string,
    body: ApprovalDecisionRequest,
  ): Promise<SessionSnapshot>;
  updateSessionModel(
    sessionId: string,
    body: UpdateSessionModelRequest,
  ): Promise<SessionSnapshot>;
  reloadConfig(): Promise<ConfigReloadResponse>;
  stopService(body?: ServiceStopRequest): Promise<ServiceStopResponse>;
  streamEvents(
    sessionId: string,
    options: Omit<StreamOptions, never>,
  ): EventSubscription;
}

class TypedCodeClientImpl implements TypedCodeClient {
  readonly protocolVersion: ProtocolVersion = PROTOCOL_VERSION;
  readonly baseUrl: string;
  readonly #token: string;
  readonly #fetch: FetchLike;

  constructor(options: ClientOptions) {
    const baseUrl = options.baseUrl.replace(/\/+$/, "");
    if (!baseUrl) {
      throw new Error("baseUrl is required");
    }
    if (!options.token) {
      throw new Error("token is required");
    }
    this.baseUrl = baseUrl;
    this.#token = options.token;
    this.#fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
  }

  async getHealth(): Promise<HealthResponse> {
    const res = await apiRequest(this.#fetch, this.baseUrl, this.#token, "/v1/health", {
      auth: false,
    });
    return readJson<HealthResponse>(res);
  }

  async listModels(opts?: { refresh?: boolean }): Promise<ModelListResponse> {
    const res = await apiRequest(this.#fetch, this.baseUrl, this.#token, "/v1/models", {
      query: { refresh: opts?.refresh },
    });
    return readJson<ModelListResponse>(res);
  }

  async listSessions(): Promise<SessionListResponse> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      "/v1/sessions",
    );
    return readJson<SessionListResponse>(res);
  }

  async createSession(body: CreateSessionRequest): Promise<CreateSessionResponse> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      "/v1/sessions",
      { method: "POST", body },
    );
    return readJson<CreateSessionResponse>(res);
  }

  async getSession(sessionId: string): Promise<SessionSnapshot> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      `/v1/sessions/${encodeURIComponent(sessionId)}`,
    );
    return readJson<SessionSnapshot>(res);
  }

  async createTurn(
    sessionId: string,
    body: CreateTurnRequest,
  ): Promise<CreateTurnResponse> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      `/v1/sessions/${encodeURIComponent(sessionId)}/turns`,
      { method: "POST", body },
    );
    return readJson<CreateTurnResponse>(res);
  }

  async abort(sessionId: string): Promise<SessionSnapshot> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      `/v1/sessions/${encodeURIComponent(sessionId)}/abort`,
      { method: "POST", body: {} },
    );
    return readJson<SessionSnapshot>(res);
  }

  async decideApproval(
    sessionId: string,
    approvalId: string,
    body: ApprovalDecisionRequest,
  ): Promise<SessionSnapshot> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      `/v1/sessions/${encodeURIComponent(sessionId)}/approvals/${encodeURIComponent(approvalId)}`,
      { method: "POST", body },
    );
    return readJson<SessionSnapshot>(res);
  }

  async updateSessionModel(
    sessionId: string,
    body: UpdateSessionModelRequest,
  ): Promise<SessionSnapshot> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      `/v1/sessions/${encodeURIComponent(sessionId)}/model`,
      { method: "POST", body },
    );
    return readJson<SessionSnapshot>(res);
  }

  async reloadConfig(): Promise<ConfigReloadResponse> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      "/v1/config/reload",
      { method: "POST", body: {} },
    );
    return readJson<ConfigReloadResponse>(res);
  }

  async stopService(
    body: ServiceStopRequest = {},
  ): Promise<ServiceStopResponse> {
    const res = await apiRequest(
      this.#fetch,
      this.baseUrl,
      this.#token,
      "/v1/service/stop",
      { method: "POST", body },
    );
    return readJson<ServiceStopResponse>(res);
  }

  streamEvents(
    sessionId: string,
    options: StreamOptions,
  ): EventSubscription {
    return streamSessionEvents(
      this.#fetch,
      this.baseUrl,
      this.#token,
      sessionId,
      options,
    );
  }
}

export function createClient(options: ClientOptions): TypedCodeClient {
  return new TypedCodeClientImpl(options);
}
