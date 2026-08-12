#!/usr/bin/env node

import { runApp } from "./app.js";
import { helpText, parseArgs, validateFlags } from "./config.js";
import {
  configureDevelopmentServer,
  formatServerCommand,
} from "./dev-config.js";
import { resolveServerCommand } from "./service-lifecycle.js";
import { runServerCommand, serverHelpText } from "./server-command.js";

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  if (argv[0] === "dev") {
    process.exitCode = runDevelopmentCommand(argv.slice(1));
    return;
  }
  if (argv[0] === "server") {
    if (argv.length === 1 || argv[1] === "--help" || argv[1] === "-h") {
      console.log(serverHelpText());
      return;
    }
    try {
      process.exitCode = await runServerCommand(argv.slice(1));
    } catch (error) {
      console.error(error instanceof Error ? error.message : String(error));
      process.exitCode = 1;
    }
    return;
  }

  let flags;
  try {
    flags = parseArgs(argv);
  } catch (err) {
    console.error(err instanceof Error ? err.message : String(err));
    console.error(helpText());
    process.exitCode = 1;
    return;
  }

  if (flags.help) {
    console.log(helpText());
    return;
  }

  const err = validateFlags(flags);
  if (err) {
    console.error(err);
    console.error(helpText());
    process.exitCode = 1;
    return;
  }

  // Token is optional on argv; runApp fills from credentials.toml
  const code = await runApp(flags);
  process.exitCode = code;
}

function runDevelopmentCommand(argv: string[]): number {
  const [command, option, value, ...extra] = argv;
  if (command === "configure" && extra.length === 0) {
    const project = option === "--project" ? value : undefined;
    const executable = option === "--executable" ? value : undefined;
    if ((!project && !executable) || !value) {
      console.error(
        "usage: typed-code dev configure (--project <absolute-root> | --executable <absolute-path>)",
      );
      return 1;
    }
    try {
      const result = configureDevelopmentServer({ project, executable });
      console.log(`configured ${result.configPath}`);
      console.log(`direct service: ${formatServerCommand(result.command)}`);
      console.log("linked CLI: npm run dev:link (from the typed-code source root)");
      return 0;
    } catch (error) {
      console.error(error instanceof Error ? error.message : String(error));
      return 1;
    }
  }
  if (command === "status" && argv.length === 1) {
    try {
      const resolved = resolveServerCommand();
      console.log(`${resolved.kind}: ${formatServerCommand(resolved)}`);
      return 0;
    } catch (error) {
      console.error(error instanceof Error ? error.message : String(error));
      return 1;
    }
  }
  console.error(
    "usage: typed-code dev configure (--project <absolute-root> | --executable <absolute-path>) | typed-code dev status",
  );
  return 1;
}

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exitCode = 1;
});
