import { emitKeypressEvents } from "node:readline";
import { createInterface } from "node:readline/promises";
import {
  credentialsPath,
  hasAnyProviderKey,
  mergeProviderKeys,
  type LocalCredentials,
  writeCredentialsFile,
} from "./local-config.js";

export async function runProviderKeyOnboarding(
  existing: LocalCredentials,
  env: NodeJS.ProcessEnv = process.env,
): Promise<LocalCredentials> {
  if (hasAnyProviderKey(existing)) {
    return existing;
  }

  console.log("");
  console.log("typed-code setup — configure at least one provider API key");
  console.log(`Keys are stored in ${credentialsPath(env)} (mode 0600).`);
  console.log("");

  const rl = createInterface({ input: process.stdin, output: process.stdout });
  let provider: "deepseek" | "cliproxy";
  try {
    console.log("  1) DeepSeek API key");
    console.log("  2) CLIProxy / OpenAI-compatible key");
    console.log("  3) Exit");
    const choice = (await rl.question("Select [1-3]: ")).trim();
    if (choice === "3" || choice === "") {
      throw new Error("setup cancelled: at least one provider key is required");
    }
    if (choice === "1") {
      provider = "deepseek";
    } else if (choice === "2") {
      provider = "cliproxy";
    } else {
      throw new Error("invalid selection");
    }
  } finally {
    rl.close();
  }

  const label = provider === "deepseek" ? "DeepSeek" : "CLIProxy";
  const key = (await promptSecret(`${label} API key: `)).trim();
  if (!key) {
    throw new Error(`empty ${label} key`);
  }

  const patch =
    provider === "deepseek"
      ? { deepseek_api_key: key }
      : { cliproxy_api_key: key };
  const next = mergeProviderKeys(existing, patch);
  writeCredentialsFile(credentialsPath(env), next);
  console.log("Saved. Continuing…");
  console.log("");
  return next;
}

/** Read one secret without terminal echo; the non-TTY fallback is for piped setup. */
export async function promptSecret(
  prompt: string,
  input: NodeJS.ReadStream = process.stdin,
  output: NodeJS.WriteStream = process.stdout,
): Promise<string> {
  if (!input.isTTY || typeof input.setRawMode !== "function") {
    const rl = createInterface({ input, output, terminal: false });
    try {
      return await rl.question(prompt);
    } finally {
      rl.close();
    }
  }

  const { promise, resolve, reject } = Promise.withResolvers<string>();
  const wasRaw = input.isRaw;
  const wasFlowing = input.readableFlowing;
  let value = "";

  const cleanup = () => {
    input.removeListener("keypress", onKeypress);
    input.setRawMode(Boolean(wasRaw));
    if (wasFlowing !== true) input.pause();
  };
  const finish = () => {
    cleanup();
    output.write("\n");
    resolve(value);
  };
  const onKeypress = (text: string, key: { name?: string; ctrl?: boolean; meta?: boolean }) => {
    if (key.name === "return" || key.name === "enter") {
      finish();
      return;
    }
    if (key.ctrl && key.name === "c") {
      cleanup();
      output.write("\n");
      reject(new Error("setup cancelled"));
      return;
    }
    if (key.name === "backspace") {
      value = Array.from(value).slice(0, -1).join("");
      return;
    }
    if (text && !key.ctrl && !key.meta && !/[\u0000-\u001f\u007f]/u.test(text)) {
      value += text;
    }
  };

  output.write(prompt);
  emitKeypressEvents(input);
  input.setRawMode(true);
  input.resume();
  input.on("keypress", onKeypress);
  return promise;
}
