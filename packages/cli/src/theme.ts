/** ANSI themes shared by the full-screen CLI components. */

import {
  truncateToWidth,
  type EditorTheme,
  type MarkdownTheme,
  type SelectListTheme,
  type SettingsListTheme,
} from "@earendil-works/pi-tui";

const ansi = (open: number, close = 0) => (text: string) =>
  `\x1b[${open}m${text}\x1b[${close}m`;

const id = (text: string) => text;
const bold = ansi(1, 22);
const dim = ansi(2, 22);
const red = ansi(31, 39);
const green = ansi(32, 39);
const yellow = ansi(33, 39);
const blue = ansi(34, 39);
const magenta = ansi(35, 39);
const cyan = ansi(36, 39);
const underline = ansi(4, 24);

export const colors = {
  id,
  bold,
  dim,
  red,
  green,
  yellow,
  blue,
  magenta,
  cyan,
  underline,
};

export function panelFrame(lines: readonly string[], width: number): string[] {
  const innerWidth = Math.max(1, width - 4);
  const horizontal = "─".repeat(Math.max(0, width - 2));
  return [
    colors.dim(`╭${horizontal}╮`),
    ...lines.map(
      (line) =>
        `${colors.dim("│")} ${truncateToWidth(line, innerWidth, "", true)} ${colors.dim("│")}`,
    ),
    colors.dim(`╰${horizontal}╯`),
  ];
}

export const selectListTheme: SelectListTheme = {
  selectedPrefix: (text) => cyan(`› ${text}`),
  selectedText: cyan,
  description: dim,
  scrollInfo: dim,
  noMatch: yellow,
};

export const settingsListTheme: SettingsListTheme = {
  label: (text, selected) => (selected ? cyan(text) : text),
  value: (text, selected) => (selected ? bold(cyan(text)) : dim(text)),
  description: dim,
  cursor: cyan("›"),
  hint: dim,
};

export const editorTheme: EditorTheme = {
  borderColor: dim,
  selectList: selectListTheme,
};

export const markdownTheme: MarkdownTheme = {
  heading: (text) => bold(cyan(text)),
  link: underline,
  linkUrl: dim,
  code: yellow,
  codeBlock: id,
  codeBlockBorder: dim,
  quote: dim,
  quoteBorder: blue,
  hr: dim,
  listBullet: cyan,
  bold,
  italic: ansi(3, 23),
  strikethrough: ansi(9, 29),
  underline,
  highlightCode: (code) => code.split("\n").map((line) => yellow(line)),
  codeBlockIndent: "  ",
};
