#!/usr/bin/env node

import { runApp } from "./app.js";
import { helpText, parseArgs, validateFlags } from "./config.js";

async function main(): Promise<void> {
  let flags;
  try {
    flags = parseArgs(process.argv.slice(2));
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

main().catch((err) => {
  console.error(err instanceof Error ? err.message : String(err));
  process.exitCode = 1;
});
