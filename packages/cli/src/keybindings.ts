/** Map raw terminal key data to CLI actions. */

import { matchesKey } from "@earendil-works/pi-tui";

export type CliAction =
  | { type: "quit" }
  | { type: "abort" }
  | { type: "approve" }
  | { type: "reject" }
  | { type: "help" }
  | { type: "redraw" }
  | { type: "toggle_thinking" }
  | { type: "none" };

/** Map terminal input, including Kitty keyboard protocol sequences. */
export function actionFromKeyData(
  data: string,
  opts: { approvalPending: boolean; runActive: boolean },
): CliAction {
  // Ctrl+C
  if (data === "\u0003") {
    return { type: "quit" };
  }
  // Ctrl+D
  if (data === "\u0004") {
    return opts.runActive ? { type: "abort" } : { type: "quit" };
  }
  // Escape
  if (data === "\u001b" || data === "\u001b[27u") {
    return opts.runActive ? { type: "abort" } : { type: "none" };
  }
  // Ctrl+L
  if (data === "\u000c") {
    return { type: "redraw" };
  }
  // Ctrl+T
  if (matchesKey(data, "ctrl+t")) {
    return { type: "toggle_thinking" };
  }
  if (data === "?" || data === "\u001bOP") {
    return { type: "help" };
  }
  if (opts.approvalPending) {
    if (data === "y" || data === "Y") {
      return { type: "approve" };
    }
    if (data === "n" || data === "N") {
      return { type: "reject" };
    }
  }
  return { type: "none" };
}
