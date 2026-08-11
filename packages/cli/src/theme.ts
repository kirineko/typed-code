/** Minimal identity/ANSI themes for pi-tui components. */

import type { EditorTheme, SelectListTheme } from "@earendil-works/pi-tui";

const id = (s: string) => s;
const dim = (s: string) => `\x1b[2m${s}\x1b[0m`;
const cyan = (s: string) => `\x1b[36m${s}\x1b[0m`;
const green = (s: string) => `\x1b[32m${s}\x1b[0m`;
const yellow = (s: string) => `\x1b[33m${s}\x1b[0m`;
const red = (s: string) => `\x1b[31m${s}\x1b[0m`;

export const colors = { id, dim, cyan, green, yellow, red };

export const selectListTheme: SelectListTheme = {
  selectedPrefix: (t) => cyan(`› ${t}`),
  selectedText: cyan,
  description: dim,
  scrollInfo: dim,
  noMatch: yellow,
};

export const editorTheme: EditorTheme = {
  borderColor: dim,
  selectList: selectListTheme,
};
