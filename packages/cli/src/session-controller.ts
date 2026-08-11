/**
 * Session attach + command orchestration (no TUI dependency).
 */

import {
  applyEvent,
  applySnapshot,
  createSessionViewState,
  type EventSubscription,
  type ProviderName,
  type ReasoningLevel,
  type SessionViewState,
  type TypedCodeClient,
  type TypedCodeError,
} from "@typed-code/sdk";

export type ViewListener = (view: SessionViewState, notice?: string) => void;

export class SessionController {
  readonly client: TypedCodeClient;
  view: SessionViewState = createSessionViewState();
  sessionId: string | null = null;
  private sub: EventSubscription | null = null;
  private listener: ViewListener | null = null;
  private notice: string | null = null;

  constructor(client: TypedCodeClient) {
    this.client = client;
  }

  onView(listener: ViewListener): void {
    this.listener = listener;
  }

  private emit(notice?: string): void {
    if (notice !== undefined) {
      this.notice = notice;
    }
    this.listener?.(this.view, this.notice ?? undefined);
  }

  async attach(sessionId: string): Promise<void> {
    this.disposeStream();
    const snapshot = await this.client.getSession(sessionId);
    this.sessionId = sessionId;
    this.view = applySnapshot(createSessionViewState(), snapshot);
    this.view = { ...this.view, connection: "live" };
    this.startStream(sessionId, this.view.lastSequence);
    this.emit("attached");
  }

  async create(opts: {
    workspace: string;
    provider?: ProviderName | undefined;
    model?: string | undefined;
  }): Promise<void> {
    const body: {
      workspace_path: string;
      provider?: ProviderName | null;
      model?: string | null;
    } = { workspace_path: opts.workspace };
    if (opts.provider !== undefined) body.provider = opts.provider;
    if (opts.model !== undefined) body.model = opts.model;
    const { snapshot } = await this.client.createSession(body);
    await this.attach(snapshot.session_id);
  }

  private startStream(sessionId: string, after: number): void {
    this.sub = this.client.streamEvents(sessionId, {
      after,
      onOpen: () => {
        if (this.view.connection === "live") return;
        this.view = { ...this.view, connection: "live" };
        this.emit();
      },
      onEvent: (event) => {
        this.view = applyEvent(this.view, event);
        this.view = { ...this.view, connection: "live" };
        this.emit();
      },
      onReset: (snapshot) => {
        this.view = applySnapshot(this.view, snapshot);
        this.view = { ...this.view, connection: "live" };
        this.emit("snapshot reset · transcript reloaded");
      },
      onError: (err) => {
        this.view = { ...this.view, connection: "reconnecting" };
        const message =
          err && typeof err === "object" && "message" in err
            ? String((err as TypedCodeError).message)
            : String(err);
        this.emit(`reconnecting: ${message}`);
      },
    });
  }

  async submit(
    prompt: string,
    reasoningLevel: ReasoningLevel | null = null,
  ): Promise<void> {
    if (!this.sessionId) {
      throw new Error("no session attached");
    }
    if (this.view.phase !== "idle") {
      throw new Error(`cannot submit while phase=${this.view.phase}`);
    }
    const text = prompt.trim();
    if (!text) {
      throw new Error("empty prompt");
    }
    const previous = this.view;
    this.view = { ...this.view, phase: "running" };
    this.emit("turn submitted");
    try {
      await this.client.createTurn(this.sessionId, {
        prompt: text,
        reasoning_level: reasoningLevel,
      });
    } catch (error) {
      try {
        const authoritative = await this.client.getSession(this.sessionId);
        this.view = applySnapshot(this.view, authoritative);
      } catch {
        this.view = previous;
      }
      this.emit();
      throw error;
    }
    // Refresh snapshot in case events are delayed.
    const snap = await this.client.getSession(this.sessionId);
    this.view = applySnapshot(this.view, snap);
    this.emit();
  }

  async abort(): Promise<void> {
    if (!this.sessionId) {
      return;
    }
    const snap = await this.client.abort(this.sessionId);
    this.view = applySnapshot(this.view, snap);
    this.emit("aborted");
  }

  async setModel(provider: ProviderName, model: string): Promise<void> {
    if (!this.sessionId) {
      throw new Error("no session attached");
    }
    if (this.view.phase !== "idle") {
      throw new Error(`cannot switch model while phase=${this.view.phase}`);
    }
    const snap = await this.client.updateSessionModel(this.sessionId, {
      provider,
      model,
    });
    this.view = applySnapshot(this.view, snap);
    this.emit(`model → ${provider}/${model}`);
  }

  async approve(): Promise<void> {
    await this.decide("approve");
  }

  async reject(): Promise<void> {
    await this.decide("reject");
  }

  private async decide(decision: "approve" | "reject"): Promise<void> {
    if (!this.sessionId) {
      return;
    }
    const pending = this.view.snapshot?.pending_approvals[0];
    if (!pending) {
      throw new Error("no pending approval");
    }
    const snap = await this.client.decideApproval(
      this.sessionId,
      pending.approval_id,
      { decision },
    );
    this.view = applySnapshot(this.view, snap);
    this.emit(`approval ${decision}`);
  }

  /** Close SSE only — does not abort the server run. */
  dispose(): void {
    this.disposeStream();
  }

  private disposeStream(): void {
    this.sub?.close();
    this.sub = null;
  }
}
