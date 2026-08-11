import type {
  ModelInfo,
  ReasoningLevel,
  SessionSummary,
  TypedCodeClient,
} from "@typed-code/sdk";

import type { AppSessionCoordinator } from "./app-session.js";
import type { AppShell } from "./app-shell.js";
import { InfoDialog } from "./components/info-dialog.js";
import { SelectionDialog } from "./components/selection-dialog.js";
import { formatTokenCount } from "./components/status-footer.js";
import {
  groupSessionsByWorkspace,
  sessionsForWorkspace,
} from "./workspace-sessions.js";
const recentThinkingCollapse = new WeakMap<AppShell, number>();

export function handleThinkingShortcut(shell: AppShell, now = Date.now()): boolean {
  const collapsedAt = recentThinkingCollapse.get(shell);
  if (collapsedAt !== undefined && now - collapsedAt < 150) return true;
  if (shell.collapseExpandedThinking()) {
    recentThinkingCollapse.set(shell, now);
    return true;
  }
  const choices = shell.transcript.thinkingChoices();
  if (choices.length === 0) return false;
  if (choices.length === 1) {
    return shell.toggleThinking(choices[0]!.id);
  }

  const dialog = new SelectionDialog(
    "Inspect thinking",
    "Newest first · Enter expand · Esc cancel",
    choices.map((choice) => ({
      value: choice.id,
      label: choice.label,
      description: choice.description,
    })),
  );
  dialog.list.onSelect = (item) => {
    shell.modals.close();
    shell.toggleThinking(item.value);
  };
  dialog.list.onCancel = () => shell.modals.close();
  shell.modals.show(dialog, shell.editor, {
    width: "80%",
    minWidth: 48,
    maxHeight: "70%",
    margin: 1,
  });
  return true;
}


export interface ModelPickerSelection {
  model: ModelInfo;
  reasoningLevel: ReasoningLevel | null;
}

export function reasoningLevelsFor(model: ModelInfo): ReasoningLevel[] {
  return (model.capabilities?.reasoning_levels ?? []).filter(
    (level): level is ReasoningLevel =>
      level === "none" ||
      level === "low" ||
      level === "medium" ||
      level === "high" ||
      level === "xhigh" ||
      level === "max",
  );
}

export function defaultReasoningLevel(model: ModelInfo): ReasoningLevel | null {
  const levels = reasoningLevelsFor(model);
  const declared = model.capabilities?.default_reasoning_level;
  if (declared && levels.includes(declared)) return declared;
  const providerDefault = model.provider === "deepseek" ? "high" : "medium";
  if (levels.includes(providerDefault)) return providerDefault;
  return levels.at(-1) ?? null;
}


export async function openModelPicker(
  shell: AppShell,
  session: AppSessionCoordinator,
  client: TypedCodeClient,
  onSelected: (selection: ModelPickerSelection) => void,
): Promise<void> {
  const models = (await client.listModels({ refresh: true })).models;
  if (models.length === 0) {
    shell.flash("No models available · use /config");
    return;
  }
  await new Promise<void>((resolve) => {
    const dialog = new SelectionDialog(
      "Select model",
      "Availability and provider context budgets",
      models.map((model, index) => ({
        value: String(index),
        label: `${model.provider}/${model.model_id}`,
        description: `${model.availability} · ctx ${formatTokenCount(model.context_token_budget)}`,
      })),
    );
    const currentIndex = models.findIndex(
      (model) =>
        model.provider === session.draft.provider &&
        model.model_id === session.draft.model,
    );
    if (currentIndex >= 0) dialog.list.setSelectedIndex(currentIndex);
    dialog.list.onSelect = (item) => {
      const model = models[Number(item.value)];
      if (!model || model.availability !== "available") {
        shell.flash("Selected model is not available · use /config");
        return;
      }
      shell.modals.close();
      const levels = reasoningLevelsFor(model);
      if (levels.length === 0) {
        void commitModelSelection(shell, session, { model, reasoningLevel: null }, onSelected, resolve);
        return;
      }
      openReasoningPicker(shell, session, model, onSelected, resolve);
    };
    dialog.list.onCancel = () => {
      shell.modals.close();
      resolve();
    };
    shell.modals.show(dialog, shell.editor, {
      width: "80%",
      minWidth: 48,
      maxHeight: "70%",
      margin: 1,
    });
  });
}

export async function openResumePicker(
  shell: AppShell,
  session: AppSessionCoordinator,
  client: TypedCodeClient,
  allProjects: boolean,
): Promise<void> {
  const listed = (await client.listSessions()).sessions;
  const candidates = allProjects
    ? allProjectRows(listed)
    : currentProjectRows(listed, session.launchWorkspace);
  if (candidates.length === 0) {
    shell.flash(
      allProjects
        ? "No persisted sessions"
        : "No sessions for the current project",
    );
    return;
  }

  await new Promise<void>((resolve) => {
    const dialog = new SelectionDialog(
      allProjects ? "Resume session · all projects" : "Resume project session",
      "Newest sessions first · Esc keeps the current session",
      candidates.map((candidate, index) => ({
        value: String(index),
        label: candidate.label,
        description: `${candidate.session.model} · ${candidate.session.phase} · ${candidate.session.updated_at}`,
      })),
    );
    dialog.list.onSelect = (item) => {
      const candidate = candidates[Number(item.value)];
      if (!candidate) return;
      shell.modals.close();
      void session.resume(candidate.session.session_id).then(
        () => {
          shell.flash(`Resumed ${candidate.session.session_id.slice(0, 8)}`);
          resolve();
        },
        (error: unknown) => {
          shell.flash(errorMessage("resume failed", error));
          resolve();
        },
      );
    };
    dialog.list.onCancel = () => {
      shell.modals.close();
      resolve();
    };
    shell.modals.show(dialog, shell.editor, {
      width: "86%",
      minWidth: 52,
      maxHeight: "75%",
      margin: 1,
    });
  });
}

export function openInfo(shell: AppShell, title: string, body: string): void {
  const dialog = new InfoDialog(title, body, () => shell.modals.close());
  shell.modals.show(dialog, shell.editor, {
    width: "80%",
    minWidth: 40,
    maxHeight: "80%",
    margin: 1,
  });
}

export function detailedStatus(session: AppSessionCoordinator): string {
  const state = session.state;
  const view = session.view;
  const lines = [
    `mode: ${state.kind}`,
    `workspace: ${state.draft.workspace}`,
    `model: ${state.draft.provider}/${state.draft.model}`,
    `thinking intensity: ${state.draft.reasoningLevel ?? "provider default"}`,
    `session: ${session.controller.sessionId ?? "not persisted"}`,
    `connection: ${view?.connection ?? "draft"}`,
    `phase: ${view?.phase ?? "draft"}`,
    `event sequence: ${view?.lastSequence ?? 0}`,
    `context: ${formatTokenCount(view?.lastUsage?.total_tokens)} / ${formatTokenCount(view?.contextBudget ?? state.draft.contextBudget)}`,
    `input/output: ${formatTokenCount(view?.lastUsage?.input_tokens)} / ${formatTokenCount(view?.lastUsage?.output_tokens)}`,
  ];
  return lines.join("\n");
}

function reasoningDescription(model: ModelInfo, level: ReasoningLevel): string {
  switch (level) {
    case "none":
      return "Disable reasoning";
    case "low":
      return "Faster, lighter reasoning";
    case "medium":
      return model.provider === "cliproxy"
        ? "Balanced reasoning (OpenAI default)"
        : "Balanced reasoning";
    case "high":
      return model.provider === "deepseek"
        ? "Deep reasoning (DeepSeek default)"
        : "Deep reasoning";
    case "xhigh":
      return "Extended reasoning";
    case "max":
      return "Maximum reasoning";
  }
}

function openReasoningPicker(
  shell: AppShell,
  session: AppSessionCoordinator,
  model: ModelInfo,
  onSelected: (selection: ModelPickerSelection) => void,
  resolve: () => void,
): void {
  const levels = reasoningLevelsFor(model);
  const dialog = new SelectionDialog(
    `Select thinking intensity · ${model.model_id}`,
    "Reasoning effort for future turns",
    levels.map((level) => ({
      value: level,
      label: level,
      description: reasoningDescription(model, level),
    })),
  );
  const preferred =
    session.draft.provider === model.provider && session.draft.model === model.model_id
      ? session.draft.reasoningLevel
      : defaultReasoningLevel(model);
  const initialLevel = preferred ?? defaultReasoningLevel(model);
  const selectedIndex = initialLevel ? levels.indexOf(initialLevel) : -1;
  dialog.list.setSelectedIndex(selectedIndex >= 0 ? selectedIndex : 0);
  dialog.list.onSelect = (item) => {
    shell.modals.close();
    void commitModelSelection(
      shell,
      session,
      { model, reasoningLevel: item.value as ReasoningLevel },
      onSelected,
      resolve,
    );
  };
  dialog.list.onCancel = () => {
    shell.modals.close();
    resolve();
  };
  shell.modals.show(dialog, shell.editor, {
    width: "64%",
    minWidth: 44,
    maxHeight: "60%",
    margin: 1,
  });
}

async function commitModelSelection(
  shell: AppShell,
  session: AppSessionCoordinator,
  selection: ModelPickerSelection,
  onSelected: (selection: ModelPickerSelection) => void,
  resolve: () => void,
): Promise<void> {
  try {
    await applyModel(session, selection);
    onSelected(selection);
  } catch (error) {
    shell.flash(errorMessage("model change failed", error));
  } finally {
    resolve();
  }
}

function applyModel(
  session: AppSessionCoordinator,
  selection: ModelPickerSelection,
): Promise<void> {
  const { model, reasoningLevel } = selection;
  return session.setModel(
    model.provider,
    model.model_id,
    model.context_token_budget ?? null,
    reasoningLevel,
  );
}

interface SessionRow {
  session: SessionSummary;
  label: string;
}

function currentProjectRows(
  sessions: readonly SessionSummary[],
  workspace: string,
): SessionRow[] {
  return sessionsForWorkspace(sessions, workspace).map((item) => ({
    session: item,
    label: `${item.session_id.slice(0, 12)} · ${item.model}`,
  }));
}

function allProjectRows(sessions: readonly SessionSummary[]): SessionRow[] {
  return groupSessionsByWorkspace(sessions).flatMap((group) =>
    group.sessions.map((item) => ({
      session: item,
      label: `${group.label} · ${item.session_id.slice(0, 8)}`,
    })),
  );
}

function errorMessage(prefix: string, error: unknown): string {
  return `${prefix}: ${error instanceof Error ? error.message : String(error)}`;
}
