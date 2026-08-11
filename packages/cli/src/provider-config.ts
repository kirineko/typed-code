import type { Component, SettingItem } from "@earendil-works/pi-tui";
import { SettingsList, TuiAltScreen } from "@earendil-works/pi-tui";
import type { ProviderName, TypedCodeClient } from "@typed-code/sdk";

import { FramedDialog } from "./components/info-dialog.js";
import { withTimeout } from "./async.js";
import {
  credentialsPath,
  mergeProviderKeys,
  type LocalCredentials,
  writeCredentialsFile,
} from "./local-config.js";
import { ModalCoordinator } from "./modal-coordinator.js";
import { SecretPrompt } from "./secret-input.js";
import { settingsListTheme } from "./theme.js";

export interface ProviderConfigurationOptions {
  tui: TuiAltScreen;
  modals: ModalCoordinator;
  client: TypedCodeClient;
  credentials: LocalCredentials;
  returnFocus: Component | null;
  provider?: ProviderName;
  credentialsFile?: string;
}

export function configureProvider(
  options: ProviderConfigurationOptions,
): Promise<LocalCredentials | null> {
  let currentCredentials = options.credentials;
  return new Promise((resolve) => {
    const finish = (credentials: LocalCredentials | null) => {
      options.modals.close();
      resolve(credentials);
    };

    const save = (
      provider: ProviderName,
      value: string,
      onActivated: () => void,
    ) => {
      const key = value.trim();
      if (!key) {
        options.tui.flash("API key cannot be empty");
        return;
      }
      const next = mergeProviderKeys(
        currentCredentials,
        provider === "deepseek"
          ? { deepseek_api_key: key }
          : { cliproxy_api_key: key },
      );
      try {
        writeCredentialsFile(options.credentialsFile ?? credentialsPath(), next);
        currentCredentials = next;
      } catch (error) {
        options.tui.flash(errorMessage("credential save failed", error), 5000);
        return;
      }
      void withTimeout(options.client.reloadConfig(), 8_000, "reload").then(
        () => onActivated(),
        (error: unknown) => {
          options.tui.flash(
            errorMessage("saved to disk; activation failed", error),
            6000,
          );
        },
      );
    };

    const createSecret = (
      provider: ProviderName,
      onActivated: () => void,
      onCancel: () => void,
    ) =>
      new SecretPrompt(
        `${provider} API key (stored securely):`,
        (value) => save(provider, value, onActivated),
        onCancel,
      );

    const openProviders = () => {
      const settings = new SettingsList(
        [
          providerSetting("deepseek", currentCredentials, createSecret),
          providerSetting("cliproxy", currentCredentials, createSecret),
        ],
        6,
        settingsListTheme,
        () => finish(currentCredentials),
        () => finish(null),
      );
      options.modals.show(
        new FramedDialog(
          "Provider configuration",
          "Select a provider · Enter edit · Esc close",
          settings,
        ),
        options.returnFocus,
        {
          width: "70%",
          minWidth: 44,
          maxHeight: 16,
          margin: 1,
        },
      );
    };

    if (options.provider) {
      const provider = options.provider;
      const prompt = createSecret(
        provider,
        () => finish(currentCredentials),
        openProviders,
      );
      options.modals.show(
        new FramedDialog(
          `Configure ${provider}`,
          "Credential is masked and stored with owner-only permissions",
          prompt,
        ),
        options.returnFocus,
        {
          width: "70%",
          minWidth: 40,
          maxHeight: 12,
          margin: 1,
        },
      );
    } else {
      openProviders();
    }
  });
}

function providerSetting(
  provider: ProviderName,
  credentials: LocalCredentials,
  createSecret: (
    provider: ProviderName,
    onActivated: () => void,
    onCancel: () => void,
  ) => SecretPrompt,
): SettingItem {
  const configured =
    provider === "deepseek"
      ? Boolean(credentials.deepseek_api_key?.trim())
      : Boolean(credentials.cliproxy_api_key?.trim());
  return {
    id: provider,
    label: provider,
    description: configured ? "configured · Enter to replace" : "missing credentials",
    currentValue: configured ? "configured" : "missing",
    submenu: (_value, done) =>
      createSecret(
        provider,
        () => done("configured"),
        () => done(),
      ),
  };
}

function errorMessage(prefix: string, error: unknown): string {
  return `${prefix}: ${error instanceof Error ? error.message : String(error)}`;
}
