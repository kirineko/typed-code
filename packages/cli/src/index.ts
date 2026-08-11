/**
 * typed-code interactive CLI — public testable surface.
 */

export { runApp } from "./app.js";
export {
  AppSessionCoordinator,
  type AppSessionState,
  type DraftSession,
} from "./app-session.js";
export {
  deriveAgentActivity,
  type ActivitySource,
  type AgentActivity,
  type AgentActivityKind,
} from "./activity.js";
export {
  CommandRegistry,
  commandHelpText,
  type CommandDefinition,
  type CommandRuntime,
} from "./commands.js";
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
  modelPreferencePath,
  parseSimpleToml,
  readModelPreference,
  writeModelPreference,
  type LocalCredentials,
  type ModelPreference,
} from "./local-config.js";
export { SessionController } from "./session-controller.js";
export {
  isSlashCommand,
  parseSlash,
  shouldRecordInHistory,
  slashHelpText,
} from "./slash.js";
export { probeService } from "./service-lifecycle.js";
export { SecretInput } from "./secret-input.js";
export { formatTokenCount } from "./components/status-footer.js";
export {
  groupSessionsByWorkspace,
  normalizeWorkspace,
  sessionsForWorkspace,
  type ProjectSessionGroup,
  type WorkspaceIdentity,
} from "./workspace-sessions.js";
