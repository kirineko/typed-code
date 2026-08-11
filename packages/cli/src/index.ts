/**
 * typed-code interactive CLI — public testable surface.
 */

export { runApp } from "./app.js";
export {
  helpText,
  parseArgs,
  validateFlags,
  type CliFlags,
} from "./config.js";
export { actionFromKeyData, type CliAction } from "./keybindings.js";
export {
  generateServerToken,
  hasAnyProviderKey,
  parseSimpleToml,
  type LocalCredentials,
} from "./local-config.js";
export {
  canSubmit,
  formatApprovalHint,
  formatConnectionError,
  formatStatusLine,
  formatToolLine,
  formatTranscriptItem,
  isRunActive,
} from "./render/format.js";
export { SessionController } from "./session-controller.js";
export {
  isSlashCommand,
  parseSlash,
  shouldRecordInHistory,
  slashHelpText,
} from "./slash.js";
export { probeService } from "./service-lifecycle.js";
export { SecretInput } from "./secret-input.js";
