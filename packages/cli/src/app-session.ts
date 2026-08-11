import type {
  ProviderName,
  ReasoningLevel,
  SessionViewState,
  TypedCodeClient,
} from "@typed-code/sdk";

import { SessionController } from "./session-controller.js";

export interface DraftSession {
  workspace: string;
  provider: ProviderName;
  model: string;
  contextBudget: number | null;
  reasoningLevel: ReasoningLevel | null;
}

export type AppSessionState =
  | { kind: "draft"; draft: DraftSession }
  | { kind: "creating"; draft: DraftSession }
  | { kind: "attached"; draft: DraftSession; controller: SessionController };

export type AppSessionListener = (state: AppSessionState) => void;

export class AppSessionCoordinator {
  readonly client: TypedCodeClient;
  readonly launchWorkspace: string;
  readonly controller: SessionController;
  state: AppSessionState;
  private listener: AppSessionListener | null = null;

  constructor(client: TypedCodeClient, draft: DraftSession) {
    this.client = client;
    this.launchWorkspace = draft.workspace;
    this.controller = new SessionController(client);
    this.state = { kind: "draft", draft };
    this.controller.onView(() => {
      if (this.state.kind === "attached") {
        this.emit();
      }
    });
  }

  onState(listener: AppSessionListener): void {
    this.listener = listener;
  }

  get view(): SessionViewState | null {
    return this.state.kind === "attached" ? this.controller.view : null;
  }

  get draft(): DraftSession {
    return this.state.draft;
  }

  async submit(prompt: string): Promise<void> {
    const text = prompt.trim();
    if (!text) {
      throw new Error("empty prompt");
    }
    if (this.state.kind === "creating") {
      throw new Error("session creation already in progress");
    }
    if (this.state.kind === "attached") {
      await this.controller.submit(text, this.state.draft.reasoningLevel);
      return;
    }

    const draft = this.state.draft;
    this.state = { kind: "creating", draft };
    this.emit();
    try {
      await this.controller.create({
        workspace: draft.workspace,
        provider: draft.provider,
        model: draft.model,
      });
    } catch (error) {
      this.state = { kind: "draft", draft };
      this.emit();
      throw error;
    }

    this.state = { kind: "attached", draft, controller: this.controller };
    this.emit();
    await this.controller.submit(text, draft.reasoningLevel);
  }

  async resume(sessionId: string): Promise<void> {
    if (this.state.kind === "creating") {
      throw new Error("session creation already in progress");
    }
    await this.controller.attach(sessionId);
    const snapshot = this.controller.view.snapshot;
    if (!snapshot) {
      throw new Error("session snapshot unavailable after attach");
    }
    const previous = this.state.draft;
    const sameModel =
      previous.provider === snapshot.provider && previous.model === snapshot.model;
    const draft: DraftSession = {
      workspace: snapshot.workspace_path,
      provider: snapshot.provider,
      model: snapshot.model,
      contextBudget: this.controller.view.contextBudget,
      reasoningLevel: sameModel ? previous.reasoningLevel : null,
    };
    this.state = { kind: "attached", draft, controller: this.controller };
    this.emit();
  }

  newDraft(): void {
    if (this.state.kind === "creating") {
      throw new Error("session creation already in progress");
    }
    const previous = this.state.draft;
    this.controller.dispose();
    this.state = {
      kind: "draft",
      draft: { ...previous, workspace: this.launchWorkspace },
    };
    this.emit();
  }

  async setModel(
    provider: ProviderName,
    model: string,
    contextBudget: number | null,
    reasoningLevel: ReasoningLevel | null,
  ): Promise<void> {
    if (this.state.kind === "creating") {
      throw new Error("session creation already in progress");
    }
    if (this.state.kind === "attached") {
      await this.controller.setModel(provider, model);
    }
    const draft = {
      ...this.state.draft,
      provider,
      model,
      contextBudget,
      reasoningLevel,
    };
    this.state =
      this.state.kind === "attached"
        ? { kind: "attached", draft, controller: this.controller }
        : { kind: "draft", draft };
    this.emit();
  }

  setContextBudget(contextBudget: number | null): void {
    const draft = { ...this.state.draft, contextBudget };
    if (this.state.kind === "attached") {
      this.controller.view = { ...this.controller.view, contextBudget };
      this.state = { kind: "attached", draft, controller: this.controller };
    } else if (this.state.kind === "creating") {
      this.state = { kind: "creating", draft };
    } else {
      this.state = { kind: "draft", draft };
    }
    this.emit();
  }

  dispose(): void {
    this.controller.dispose();
  }

  private emit(): void {
    this.listener?.(this.state);
  }
}
