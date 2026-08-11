import type {
  AutocompleteItem,
  SlashCommand,
} from "@earendil-works/pi-tui";
import type {
  ModelInfo,
  ProviderName,
  ReasoningLevel,
  SessionSummary,
  TypedCodeClient,
} from "@typed-code/sdk";

import type { AppSessionCoordinator } from "./app-session.js";
import { defaultReasoningLevel } from "./interactive-workflows.js";
import {
  groupSessionsByWorkspace,
  sessionsForWorkspace,
} from "./workspace-sessions.js";

export interface CommandRuntime {
  client: TypedCodeClient;
  session: AppSessionCoordinator;
  openHelp(): void;
  openConfig(provider?: ProviderName): void;
  openModelPicker(): Promise<void>;
  rememberModel(
    provider: ProviderName,
    model: string,
    reasoningLevel: ReasoningLevel | null,
  ): void;
  openResumePicker(allProjects: boolean): Promise<void>;
  openStatus(): void;
  openKeys(): void;
  quit(): void;
  flash(message: string): void;
}

export interface CommandDefinition {
  name: string;
  aliases?: readonly string[];
  description: string;
  argumentHint?: string;
  unavailable?(runtime: CommandRuntime): string | null;
  complete?(prefix: string, runtime: CommandRuntime): Promise<AutocompleteItem[]>;
  execute(args: string, runtime: CommandRuntime): Promise<void> | void;
}

const DEFINITIONS: readonly CommandDefinition[] = [
  {
    name: "help",
    aliases: ["?"],
    description: "Show commands and usage",
    execute: (_args, runtime) => runtime.openHelp(),
  },
  {
    name: "model",
    description: "Select model and thinking intensity",
    argumentHint: "[provider/model]",
    unavailable: (runtime) => {
      const view = runtime.session.view;
      return view && view.phase !== "idle" ? `model requires idle; phase=${view.phase}` : null;
    },
    complete: completeModels,
    async execute(args, runtime) {
      if (!args) {
        await runtime.openModelPicker();
        return;
      }
      const models = (await runtime.client.listModels()).models;
      const selected = findModel(models, args);
      if (!selected || selected.availability !== "available") {
        runtime.flash(`model unavailable: ${args}`);
        return;
      }
      const reasoningLevel = defaultReasoningLevel(selected);
      await runtime.session.setModel(
        selected.provider,
        selected.model_id,
        selected.context_token_budget ?? null,
        reasoningLevel,
      );
      runtime.rememberModel(selected.provider, selected.model_id, reasoningLevel);
      runtime.flash(
        `model → ${selected.provider}/${selected.model_id}${
          reasoningLevel ? ` · reasoning ${reasoningLevel}` : ""
        }`,
      );
    },
  },
  {
    name: "config",
    description: "Configure provider credentials",
    argumentHint: "[deepseek|cliproxy]",
    complete: async (prefix) =>
      ["deepseek", "cliproxy"]
        .filter((value) => value.startsWith(prefix.trim().toLowerCase()))
        .map((value) => ({ value, label: value, description: "provider" })),
    execute(args, runtime) {
      const parts = args.split(/\s+/).filter(Boolean);
      if (parts.length > 1) {
        runtime.flash("credentials cannot be entered as command arguments");
        return;
      }
      const provider = parts[0];
      if (provider === "deepseek" || provider === "cliproxy") {
        runtime.openConfig(provider);
        return;
      }
      if (provider) {
        runtime.flash("usage: /config [deepseek|cliproxy]");
        return;
      }
      runtime.openConfig();
    },
  },
  {
    name: "new",
    description: "Open an unsaved session for the launch workspace",
    unavailable: (runtime) =>
      runtime.session.state.kind === "creating" ? "session creation is in progress" : null,
    execute: (_args, runtime) => runtime.session.newDraft(),
  },
  {
    name: "resume",
    description: "Resume a project session",
    argumentHint: "[--all|session-prefix]",
    unavailable: (runtime) =>
      runtime.session.state.kind === "creating" ? "session creation is in progress" : null,
    complete: completeSessions,
    async execute(args, runtime) {
      const value = args.trim();
      if (!value || value === "--all") {
        await runtime.openResumePicker(value === "--all");
        return;
      }
      const sessions = (await runtime.client.listSessions()).sessions;
      const candidates = sessionsForWorkspace(sessions, runtime.session.launchWorkspace);
      const matches = candidates.filter((item) => item.session_id.startsWith(value));
      if (matches.length !== 1) {
        runtime.flash(
          matches.length === 0
            ? `no current-project session matches ${value}`
            : `session prefix is ambiguous: ${value}`,
        );
        return;
      }
      await runtime.session.resume(matches[0]!.session_id);
    },
  },
  {
    name: "status",
    description: "Show session, connection, and usage details",
    execute: (_args, runtime) => runtime.openStatus(),
  },
  {
    name: "abort",
    description: "Cancel the active run",
    unavailable: (runtime) => {
      const phase = runtime.session.view?.phase;
      return phase === "running" || phase === "awaiting_approval"
        ? null
        : "no active run";
    },
    async execute(_args, runtime) {
      await runtime.session.controller.abort();
    },
  },
  {
    name: "keys",
    description: "Show keyboard controls",
    execute: (_args, runtime) => runtime.openKeys(),
  },
  {
    name: "quit",
    aliases: ["exit"],
    description: "Close the CLI without cancelling server runs",
    execute: (_args, runtime) => runtime.quit(),
  },
];

export class CommandRegistry {
  readonly runtime: CommandRuntime;

  constructor(runtime: CommandRuntime) {
    this.runtime = runtime;
  }

  definitions(): readonly CommandDefinition[] {
    return DEFINITIONS;
  }

  slashCommands(): SlashCommand[] {
    return DEFINITIONS.map((definition) => {
      const command: SlashCommand = {
        name: definition.name,
        description: definition.description,
      };
      if (definition.argumentHint !== undefined) {
        command.argumentHint = definition.argumentHint;
      }
      const complete = definition.complete;
      if (complete) {
        command.getArgumentCompletions = (prefix) =>
          complete(prefix, this.runtime);
      }
      return command;
    });
  }

  helpText(): string {
    return commandHelpText();
  }

  async execute(text: string): Promise<void> {
    const { command, args } = parseSlash(text);
    const name = command.slice(1);
    const definition = DEFINITIONS.find(
      (item) => item.name === name || item.aliases?.includes(name),
    );
    if (!definition) {
      this.runtime.flash(`unknown command ${command} · use /help`);
      return;
    }
    const unavailable = definition.unavailable?.(this.runtime);
    if (unavailable) {
      this.runtime.flash(unavailable);
      return;
    }
    await definition.execute(args, this.runtime);
  }
}

export function commandHelpText(): string {
  return DEFINITIONS.map((definition) => {
    const hint = definition.argumentHint ? ` ${definition.argumentHint}` : "";
    return `/${definition.name}${hint}  ${definition.description}`;
  }).join("\n");
}

export function isSlashCommand(text: string): boolean {
  return text.trimStart().startsWith("/");
}

export function parseSlash(text: string): { command: string; args: string } {
  const trimmed = text.trim();
  const space = trimmed.indexOf(" ");
  if (space === -1) return { command: trimmed.toLowerCase(), args: "" };
  return {
    command: trimmed.slice(0, space).toLowerCase(),
    args: trimmed.slice(space + 1).trim(),
  };
}

export function shouldRecordInHistory(text: string): boolean {
  return !/^\s*\/config(?:\s|$)/i.test(text);
}

function findModel(models: readonly ModelInfo[], value: string): ModelInfo | undefined {
  const normalized = value.trim();
  return models.find(
    (model) =>
      `${model.provider}/${model.model_id}` === normalized ||
      `${model.provider} ${model.model_id}` === normalized,
  );
}

async function completeModels(
  prefix: string,
  runtime: CommandRuntime,
): Promise<AutocompleteItem[]> {
  const query = prefix.trim().toLowerCase();
  const models = (await runtime.client.listModels()).models;
  return models
    .filter((model) => `${model.provider}/${model.model_id}`.toLowerCase().includes(query))
    .map((model) => ({
      value: `${model.provider}/${model.model_id}`,
      label: `${model.provider}/${model.model_id}`,
      description: `${model.availability} · ctx ${model.context_token_budget}`,
    }));
}

async function completeSessions(
  prefix: string,
  runtime: CommandRuntime,
): Promise<AutocompleteItem[]> {
  const query = prefix.trim().toLowerCase();
  const sessions = (await runtime.client.listSessions()).sessions;
  if (query.startsWith("--")) {
    return [{ value: "--all", label: "--all", description: "all projects" }];
  }
  const current = sessionsForWorkspace(sessions, runtime.session.launchWorkspace);
  return current
    .filter((session) => session.session_id.toLowerCase().startsWith(query))
    .map(sessionCompletion);
}

function sessionCompletion(session: SessionSummary): AutocompleteItem {
  return {
    value: session.session_id,
    label: session.session_id.slice(0, 12),
    description: `${session.model} · ${session.phase} · ${session.updated_at}`,
  };
}

export function groupedSessionLabels(sessions: readonly SessionSummary[]): string[] {
  return groupSessionsByWorkspace(sessions).flatMap((group) =>
    group.sessions.map(
      (session) => `${group.label} · ${session.session_id.slice(0, 8)} · ${session.model}`,
    ),
  );
}
