/**
 * Interactive chat application shell on pi-tui (single local entry).
 */

import {
  Container,
  Editor,
  ProcessTerminal,
  Text,
  type TUI,
  TuiMainScreen,
  type OverlayHandle,
  matchesKey,
} from "@earendil-works/pi-tui";
import {
  PROTOCOL_VERSION,
  createClient,
  type TypedCodeClient,
} from "@typed-code/sdk";

import type { CliFlags } from "./config.js";
import { StatusBar } from "./components/status-bar.js";
import { TranscriptView } from "./components/transcript-view.js";
import { actionFromKeyData } from "./keybindings.js";
import {
  ensureLocalCredentials,
  hasAnyProviderKey,
  type LocalCredentials,
} from "./local-config.js";
import { runProviderKeyOnboarding } from "./onboarding.js";
import { canSubmit, isRunActive } from "./render/format.js";
import {
  ensureLocalService,
  stopOwnedService,
  type ServiceHandle,
} from "./service-lifecycle.js";
import { SessionController } from "./session-controller.js";
import {
  handleSlashCommand,
  isSlashCommand,
  shouldRecordInHistory,
} from "./slash.js";
import { SecretPrompt } from "./secret-input.js";
import { colors, editorTheme } from "./theme.js";

export async function runApp(flags: CliFlags): Promise<number> {
  // 1) Local credentials + optional onboarding
  let { creds } = ensureLocalCredentials();
  if (!hasAnyProviderKey(creds)) {
    try {
      creds = await runProviderKeyOnboarding(creds);
    } catch (err) {
      console.error(err instanceof Error ? err.message : String(err));
      return 1;
    }
  }

  const token = flags.token.trim() || creds.server_token || "";
  if (!token) {
    console.error("missing server token (credentials.toml or --token)");
    return 1;
  }

  // 2) Ensure service
  let service: ServiceHandle;
  try {
    if (flags.noSpawn) {
      service = {
        baseUrl: flags.baseUrl,
        token,
        owned: false,
        child: null,
      };
    } else {
      service = await ensureLocalService({
        baseUrl: flags.baseUrl,
        token,
      });
    }
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err));
    return 1;
  }

  const client = createClient({
    baseUrl: service.baseUrl,
    token: service.token,
  });

  let health;
  try {
    health = await client.getHealth();
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`failed to reach service at ${service.baseUrl}: ${msg}`);
    if (!service.owned) {
      console.error("Start the server: uv run typed-code serve");
    }
    await stopOwnedService(service);
    return 1;
  }
  if (health.protocol_version !== PROTOCOL_VERSION) {
    console.error(
      `protocol mismatch: server=${health.protocol_version} client=${PROTOCOL_VERSION}`,
    );
    await stopOwnedService(service);
    return 1;
  }

  const controller = new SessionController(client);
  try {
    await openSession(controller, client, flags);
    await refreshContextBudget(controller, client);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`failed to open session: ${msg}`);
    await stopOwnedService(service);
    return 1;
  }

  const terminal = new ProcessTerminal();
  const tui: TUI = new TuiMainScreen(terminal);

  const root = new Container();
  const status = new StatusBar();
  const transcript = new TranscriptView();
  const spacer = new Text("");
  const editor = new Editor(tui, editorTheme);

  root.addChild(status);
  root.addChild(transcript);
  root.addChild(spacer);
  root.addChild(editor);
  tui.addChild(root);
  tui.setFocus(editor);

  const refresh = (notice?: string) => {
    status.setView(controller.view, notice);
    transcript.setView(controller.view);
    editor.disableSubmit = !canSubmit(controller.view);
    tui.requestRender();
  };

  controller.onView((view, notice) => {
    status.setView(view, notice);
    transcript.setView(view);
    editor.disableSubmit = !canSubmit(view);
    tui.requestRender();
  });
  refresh("ready · /help for commands");

  let localCreds: LocalCredentials = creds;

  let slashBusy = false;
  editor.onSubmit = (text) => {
    void (async () => {
      if (slashBusy) {
        return;
      }
      try {
        if (isSlashCommand(text)) {
          slashBusy = true;
          editor.disableSubmit = true;
          if (shouldRecordInHistory(text)) {
            editor.addToHistory(text);
          }
          editor.setText("");
          try {
            await handleSlashCommand({
              text,
              client,
              controller,
              creds: localCreds,
              onCreds: (c) => {
                localCreds = c;
              },
              setNotice: (msg) => {
                status.setNotice(msg);
                tui.requestRender();
              },
              promptProviderKey: (provider) =>
                promptProviderKey(tui, editor, provider),
            });
            await refreshContextBudget(controller, client);
          } finally {
            slashBusy = false;
            editor.disableSubmit = !canSubmit(controller.view);
            tui.setFocus(editor);
            refresh();
          }
          return;
        }
        await controller.submit(text);
        editor.addToHistory(text);
        editor.setText("");
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        status.setNotice(msg);
        slashBusy = false;
        tui.setFocus(editor);
        tui.requestRender();
      }
    })();
  };

  let exited = false;
  const quit = () => {
    if (exited) {
      return;
    }
    exited = true;
    controller.dispose();
    try {
      tui.stop();
    } catch {
      // ignore
    }
    void stopOwnedService(service).catch((error) => {
      console.error(
        `failed to stop local service: ${error instanceof Error ? error.message : String(error)}`,
      );
      process.exitCode = 1;
    });
  };

  tui.addInputListener((data) => {
    if (matchesKey(data, "ctrl+c")) {
      quit();
      return { consume: true };
    }

    const action = actionFromKeyData(data, {
      approvalPending: (controller.view.snapshot?.pending_approvals.length ?? 0) > 0,
      runActive: isRunActive(controller.view),
    });

    switch (action.type) {
      case "quit":
        quit();
        return { consume: true };
      case "abort":
        void controller.abort().catch((err) => {
          status.setNotice(err instanceof Error ? err.message : String(err));
          tui.requestRender();
        });
        return { consume: true };
      case "approve":
        void controller.approve().catch((err) => {
          status.setNotice(err instanceof Error ? err.message : String(err));
          tui.requestRender();
        });
        return { consume: true };
      case "reject":
        void controller.reject().catch((err) => {
          status.setNotice(err instanceof Error ? err.message : String(err));
          tui.requestRender();
        });
        return { consume: true };
      case "help":
        status.toggleHelp();
        tui.requestRender();
        return { consume: true };
      case "redraw":
        tui.requestRender();
        return { consume: true };
      default:
        return undefined;
    }
  });

  const onSignal = () => quit();
  process.once("SIGINT", onSignal);
  process.once("SIGTERM", onSignal);

  tui.start();
  return 0;
}

function promptProviderKey(
  tui: TUI,
  editor: Editor,
  provider: "deepseek" | "cliproxy",
): Promise<string | null> {
  const { promise, resolve } = Promise.withResolvers<string | null>();
  let settled = false;
  let handle: OverlayHandle;
  const finish = (value: string | null) => {
    if (settled) return;
    settled = true;
    prompt.clear();
    handle.hide();
    tui.setFocus(editor);
    tui.requestRender();
    resolve(value);
  };
  const prompt = new SecretPrompt(
    `Enter ${provider} API key (masked · Esc cancels)`,
    (value) => finish(value.trim() || null),
    () => finish(null),
  );
  handle = tui.showOverlay(prompt, {
    anchor: "center",
    width: "70%",
    minWidth: 40,
    maxHeight: 4,
  });
  handle.focus();
  tui.requestRender();
  return promise;
}


async function refreshContextBudget(
  controller: SessionController,
  client: TypedCodeClient,
): Promise<void> {
  const snap = controller.view.snapshot;
  if (!snap) {
    return;
  }
  try {
    const models = await client.listModels();
    const match = models.models.find(
      (m) => m.provider === snap.provider && m.model_id === snap.model,
    );
    const budget = match?.context_token_budget ?? null;
    controller.view = { ...controller.view, contextBudget: budget };
  } catch {
    // ignore catalog errors for status display
  }
}

async function openSession(
  controller: SessionController,
  client: TypedCodeClient,
  flags: CliFlags,
): Promise<void> {
  if (flags.sessionId) {
    await controller.attach(flags.sessionId);
    return;
  }
  if (flags.createNew || !flags.sessionId) {
    if (!flags.createNew) {
      const listed = await client.listSessions();
      if (listed.sessions.length > 0) {
        const picked = await pickSessionInteractively(listed.sessions);
        if (picked) {
          await controller.attach(picked);
          return;
        }
      }
    }
    const createOpts: {
      workspace: string;
      provider?: "deepseek" | "cliproxy";
      model?: string;
    } = { workspace: flags.workspace };
    if (flags.provider) createOpts.provider = flags.provider;
    if (flags.model) createOpts.model = flags.model;
    await controller.create(createOpts);
  }
}

async function pickSessionInteractively(
  sessions: { session_id: string; model: string; phase: string; updated_at: string }[],
): Promise<string | null> {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    return null;
  }
  const { createInterface } = await import("node:readline/promises");
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    console.log("Sessions (Enter empty to create new):");
    sessions.slice(0, 20).forEach((s, i) => {
      console.log(
        `  [${i}] ${s.session_id.slice(0, 8)}…  ${s.model}  ${s.phase}  ${s.updated_at}`,
      );
    });
    const answer = (await rl.question("Select index (or empty): ")).trim();
    if (!answer) {
      return null;
    }
    const idx = Number(answer);
    if (!Number.isInteger(idx) || idx < 0 || idx >= sessions.length) {
      console.log("invalid selection; creating new session");
      return null;
    }
    return sessions[idx]?.session_id ?? null;
  } finally {
    rl.close();
  }
}
