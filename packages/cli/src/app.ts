import {
  CombinedAutocompleteProvider,
  Editor,
  Loader,
  ProcessTerminal,
  Text,
  TuiAltScreen,
  VStack,
  matchesKey,
} from "@earendil-works/pi-tui";
import {
  PROTOCOL_VERSION,
  createClient,
  type ModelInfo,
  type ProviderName,
  type ReasoningLevel,
  type TypedCodeClient,
} from "@typed-code/sdk";

import { withTimeout } from "./async.js";
import { AppSessionCoordinator, type DraftSession } from "./app-session.js";
import { AppShell } from "./app-shell.js";
import { CommandRegistry, isSlashCommand, shouldRecordInHistory } from "./commands.js";
import { ApprovalDialog } from "./components/approval-dialog.js";
import { InfoDialog } from "./components/info-dialog.js";
import type { CliFlags } from "./config.js";
import {
  detailedStatus,
  defaultReasoningLevel,
  handleThinkingShortcut,
  openInfo,
  openModelPicker,
  openResumePicker,
  reasoningLevelsFor,
} from "./interactive-workflows.js";
import { actionFromKeyData } from "./keybindings.js";
import {
  ensureLocalCredentials,
  hasAnyProviderKey,
  modelPreferencePath,
  readModelPreference,
  writeModelPreference,
  type LocalCredentials,
  type ModelPreference,
} from "./local-config.js";
import { ModalCoordinator } from "./modal-coordinator.js";
import { configureProvider } from "./provider-config.js";
import {
  ensureLocalService,
  stopOwnedService,
  type ServiceHandle,
} from "./service-lifecycle.js";
import { colors, editorTheme } from "./theme.js";
import { normalizeWorkspace } from "./workspace-sessions.js";

export async function runApp(flags: CliFlags): Promise<number> {
  const local = ensureLocalCredentials();
  let localCredentials = local.creds;
  const preferencePath = modelPreferencePath();
  const modelPreference = readModelPreference(preferencePath);
  const token = flags.token.trim() || localCredentials.server_token || "";
  if (!token) {
    console.error("missing server token in credentials.toml");
    return 1;
  }

  const tui = new TuiAltScreen(new ProcessTerminal());
  const startupMessage = new Text(colors.bold("typed-code"), 0, 0);
  const startupLoader = new Loader(
    tui,
    colors.cyan,
    colors.dim,
    "Starting local service…",
  );
  tui.setLayoutRoot(new VStack([startupMessage, startupLoader], { gap: 1 }));
  tui.start();
  startupLoader.start();

  let service: ServiceHandle | null = null;
  const failStartup = async (message: string): Promise<number> => {
    startupLoader.stop();
    startupMessage.setText(colors.red(`typed-code startup failed\n\n${message}`));
    tui.requestRender(true);
    tui.renderNow(true);
    tui.stop();
    if (service) await stopOwnedService(service);
    return 1;
  };

  try {
    service = flags.noSpawn
      ? {
          baseUrl: flags.baseUrl,
          token,
          owned: false,
          child: null,
        }
      : await ensureLocalService({ baseUrl: flags.baseUrl, token });
  } catch (error) {
    return failStartup(errorMessage("service startup failed", error));
  }

  const client = createClient({ baseUrl: service.baseUrl, token: service.token });
  let health;
  try {
    startupLoader.setMessage("Negotiating service protocol…");
    health = await withTimeout(client.getHealth(), 8_000, "health negotiation");
  } catch (error) {
    return failStartup(errorMessage(`cannot reach ${service.baseUrl}`, error));
  }
  if (health.protocol_version !== PROTOCOL_VERSION) {
    return failStartup(
      `protocol mismatch: server=${health.protocol_version} client=${PROTOCOL_VERSION}`,
    );
  }

  const bootstrapModals = new ModalCoordinator(tui);
  let models: ModelInfo[];
  try {
    models = await listModels(client, true);
  } catch (error) {
    return failStartup(errorMessage("model availability failed", error));
  }
  while (!hasAnyProviderKey(localCredentials) || !availableModels(models).length) {
    startupLoader.stop();
    startupMessage.setText(
      colors.yellow("Provider setup required before the composer can be enabled"),
    );
    tui.requestRender();
    const configured = await configureProvider({
      tui,
      modals: bootstrapModals,
      client,
      credentials: localCredentials,
      returnFocus: null,
    });
    if (!configured) {
      return failStartup("provider setup cancelled");
    }
    localCredentials = configured;
    startupLoader.start();
    startupLoader.setMessage("Refreshing model availability…");
    try {
      models = await listModels(client, true);
    } catch (error) {
      return failStartup(errorMessage("model availability failed", error));
    }
  }

  let workspace;
  try {
    startupLoader.setMessage("Resolving workspace…");
    workspace = await normalizeWorkspace(flags.workspace);
  } catch (error) {
    return failStartup(errorMessage("invalid workspace", error));
  }

  const selected = selectInitialModel(
    models,
    flags,
    modelPreference,
    health.default_provider,
    health.default_model,
  );
  if (!selected) {
    return failStartup("no available model matches the requested provider/model");
  }
  const availableReasoning = reasoningLevelsFor(selected);
  const rememberedReasoning =
    modelPreference?.provider === selected.provider &&
    modelPreference.model === selected.model_id &&
    modelPreference.reasoning_level &&
    availableReasoning.includes(modelPreference.reasoning_level)
      ? modelPreference.reasoning_level
      : null;
  const reasoningLevel = rememberedReasoning ?? defaultReasoningLevel(selected);

  const draft: DraftSession = {
    workspace: workspace.canonicalPath,
    provider: selected.provider,
    model: selected.model_id,
    contextBudget: selected.context_token_budget ?? null,
    reasoningLevel,
  };
  const session = new AppSessionCoordinator(client, draft);
  if (flags.sessionId) {
    try {
      await session.resume(flags.sessionId);
    } catch (error) {
      return failStartup(errorMessage("explicit session resume failed", error));
    }
  }
  const editor = new Editor(tui, editorTheme, { paddingX: 1 });
  const shell = new AppShell(tui, editor);
  startupLoader.stop();

  let exited = false;
  let registry: CommandRegistry | null = null;
  let approvalPresented: string | null = null;
  let budgetLookupKey = "";

  const quit = () => {
    if (exited) return;
    exited = true;
    session.dispose();
    try {
      tui.stop();
    } finally {
      process.removeListener("SIGINT", onSignal);
      process.removeListener("SIGTERM", onSignal);
    }
    if (service) {
      void stopOwnedService(service).catch((error: unknown) => {
        console.error(errorMessage("failed to stop local service", error));
        process.exitCode = 1;
      });
    }
  };
  const onSignal = () => quit();

  const commandRuntime = {
    client,
    session,
    openHelp() {
      openInfo(shell, "Commands", registry?.helpText() ?? "Commands unavailable");
    },
    openConfig(provider?: ProviderName) {
      void configureProvider({
        tui,
        modals: shell.modals,
        client,
        credentials: localCredentials,
        returnFocus: shell.editor,
        ...(provider ? { provider } : {}),
      }).then((configured) => {
        if (!configured) return;
        localCredentials = configured;
        shell.flash("Configuration saved and activated");
        void refreshBudget(session, client, true);
      });
    },
    async openModelPicker() {
      await openModelPicker(shell, session, client, ({ model, reasoningLevel }) => {
        writeModelPreference(preferencePath, {
          provider: model.provider,
          model: model.model_id,
          ...(reasoningLevel ? { reasoning_level: reasoningLevel } : {}),
        });
      });
    },
    rememberModel(
      provider: ProviderName,
      model: string,
      reasoningLevel: ReasoningLevel | null,
    ) {
      writeModelPreference(preferencePath, {
        provider,
        model,
        ...(reasoningLevel ? { reasoning_level: reasoningLevel } : {}),
      });
    },
    async openResumePicker(allProjects: boolean) {
      await openResumePicker(shell, session, client, allProjects);
    },
    openStatus() {
      openInfo(shell, "Session status", detailedStatus(session));
    },
    openKeys() {
      openInfo(
        shell,
        "Keyboard controls",
        [
          "Enter submit",
          "Alt/Shift/Ctrl+Enter newline",
          "Tab complete command or path",
          "Esc/Ctrl+D abort active run",
          "y/n approve or reject",
          "Ctrl+End latest output",
          "Ctrl+T inspect selected thinking / collapse expanded thinking",
          "Ctrl+L redraw",
          "Ctrl+C quit without cancelling the server run",
        ].join("\n"),
      );
    },
    quit,
    flash(message: string) {
      shell.flash(message);
    },
  };
  registry = new CommandRegistry(commandRuntime);
  editor.setAutocompleteProvider(
    new CombinedAutocompleteProvider(registry.slashCommands(), workspace.canonicalPath),
  );

  const presentApproval = () => {
    const pending = session.view?.snapshot?.pending_approvals[0];
    if (!pending) {
      approvalPresented = null;
      return;
    }
    if (approvalPresented === pending.approval_id || shell.modals.isOpen) return;
    approvalPresented = pending.approval_id;
    const dialog = new ApprovalDialog(
      pending,
      async (decision) => {
        if (decision === "approve") {
          await session.controller.approve();
        } else {
          await session.controller.reject();
        }
        shell.modals.close();
      },
      () => shell.modals.close(),
      () => shell.requestRender(),
    );
    shell.modals.show(dialog, shell.editor, {
      width: "62%",
      minWidth: 48,
      maxHeight: 16,
      margin: 1,
    });
  };

  session.onState((state) => {
    shell.sync(state);
    presentApproval();
    if (state.kind === "attached") {
      const snapshot = state.controller.view.snapshot;
      const lookupKey = snapshot ? `${snapshot.provider}/${snapshot.model}` : "";
      if (lookupKey && lookupKey !== budgetLookupKey) {
        budgetLookupKey = lookupKey;
        void refreshBudget(session, client, false);
      }
    }
  });

  let commandBusy = false;
  editor.onSubmit = (text) => {
    void (async () => {
      if (commandBusy) return;
      if (isSlashCommand(text)) {
        commandBusy = true;
        editor.disableSubmit = true;
        if (shouldRecordInHistory(text)) editor.addToHistory(text);
        editor.setText("");
        try {
          await registry?.execute(text);
        } catch (error) {
          shell.flash(errorMessage("command failed", error));
        } finally {
          commandBusy = false;
          tui.setFocus(editor);
          shell.sync(session.state);
        }
        return;
      }

      try {
        await session.submit(text);
        editor.addToHistory(text);
        editor.setText("");
      } catch (error) {
        shell.flash(errorMessage("submit failed", error), 5000);
        shell.sync(session.state);
      }
    })();
  };

  tui.addInputListener((data) => {
    if (matchesKey(data, "ctrl+c")) {
      quit();
      return { consume: true };
    }
    if (matchesKey(data, "ctrl+end")) {
      shell.scrollToEnd();
      return { consume: true };
    }
    if (shell.modals.isOpen) return undefined;

    const view = session.view;
    const action = actionFromKeyData(data, {
      approvalPending: (view?.snapshot?.pending_approvals.length ?? 0) > 0,
      runActive: view?.phase === "running" || view?.phase === "awaiting_approval",
    });
    switch (action.type) {
      case "quit":
        quit();
        return { consume: true };
      case "abort":
        shell.sync(session.state, { cancelling: true });
        void session.controller.abort().catch((error: unknown) =>
          shell.flash(errorMessage("abort failed", error)),
        );
        return { consume: true };
      case "approve":
        void session.controller.approve().catch((error: unknown) =>
          shell.flash(errorMessage("approval failed", error)),
        );
        return { consume: true };
      case "reject":
        void session.controller.reject().catch((error: unknown) =>
          shell.flash(errorMessage("rejection failed", error)),
        );
        return { consume: true };
      case "help":
        if (editor.getText().length > 0 && data === "?") return undefined;
        commandRuntime.openHelp();
        return { consume: true };
      case "toggle_thinking":
        if (!handleThinkingShortcut(shell)) {
          shell.flash("No completed thinking block to inspect");
        }
        return { consume: true };
      case "redraw":
        tui.requestRender(true);
        return { consume: true };
      case "none":
        return undefined;
    }
  });

  process.once("SIGINT", onSignal);
  process.once("SIGTERM", onSignal);
  shell.sync(session.state);
  shell.flash("New session · /help commands · /resume history");
  return 0;
}

async function refreshBudget(
  session: AppSessionCoordinator,
  client: TypedCodeClient,
  refresh: boolean,
): Promise<void> {
  const snapshot = session.view?.snapshot;
  const provider = snapshot?.provider ?? session.draft.provider;
  const model = snapshot?.model ?? session.draft.model;
  try {
    const models = (await withTimeout(client.listModels({ refresh }), 8_000, "model refresh")).models;
    const selected = models.find(
      (item) => item.provider === provider && item.model_id === model,
    );
    session.setContextBudget(selected?.context_token_budget ?? null);
  } catch {
    session.setContextBudget(null);
  }
}

export function selectInitialModel(
  models: readonly ModelInfo[],
  flags: CliFlags,
  preference: ModelPreference | null,
  defaultProvider?: string,
  defaultModel?: string,
): ModelInfo | undefined {
  const available = availableModels(models);
  if (flags.provider || flags.model) {
    return available.find(
      (model) =>
        (flags.provider === undefined || model.provider === flags.provider) &&
        (flags.model === undefined || model.model_id === flags.model),
    );
  }
  if (preference) {
    const remembered = available.find(
      (model) =>
        model.provider === preference.provider && model.model_id === preference.model,
    );
    if (remembered) return remembered;
  }
  const deepseek = available.find(
    (model) =>
      model.provider === "deepseek" && model.model_id === "deepseek-v4-flash",
  );
  if (deepseek) return deepseek;
  return (
    available.find(
      (model) =>
        model.provider === defaultProvider && model.model_id === defaultModel,
    ) ?? available[0]
  );
}

function availableModels(models: readonly ModelInfo[]): ModelInfo[] {
  return models.filter((model) => model.availability === "available");
}

async function listModels(
  client: TypedCodeClient,
  refresh: boolean,
): Promise<ModelInfo[]> {
  return (
    await withTimeout(client.listModels({ refresh }), 8_000, "model availability")
  ).models;
}


function errorMessage(prefix: string, error: unknown): string {
  return `${prefix}: ${error instanceof Error ? error.message : String(error)}`;
}
