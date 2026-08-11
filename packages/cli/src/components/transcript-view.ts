import {
  Markdown,
  Text,
  type Component,
  visibleWidth,
} from "@earendil-works/pi-tui";
import type {
  SessionViewState,
  StreamingTool,
  TranscriptItem,
} from "@typed-code/sdk";

import { colors, markdownTheme } from "../theme.js";

type TranscriptBlock = Component & {
  update(value: unknown): void;
};

export interface ThinkingChoice {
  id: string;
  label: string;
  description: string;
}

class AssistantBlock implements TranscriptBlock {
  private readonly markdown = new Markdown("", 0, 0, markdownTheme);
  private streaming = false;

  update(value: unknown): void {
    const next =
      typeof value === "object" && value !== null
        ? (value as { text: string; streaming: boolean })
        : { text: String(value), streaming: false };
    this.markdown.setText(next.text);
    this.streaming = next.streaming;
  }

  invalidate(): void {
    this.markdown.invalidate();
  }

  render(width: number): string[] {
    const header = `  ${colors.green("◆")} ${colors.green(colors.bold("Agent"))}${
      this.streaming ? colors.dim(" · responding") : ""
    }`;
    const innerWidth = Math.max(1, width - 4);
    const body = this.markdown
      .render(innerWidth)
      .map((line) => `  ${colors.dim("│")} ${line}`);
    if (this.streaming) {
      const last = body.length - 1;
      if (last >= 0 && visibleWidth(body[last] ?? "") < width) {
        body[last] = `${body[last]}${colors.cyan("▌")}`;
      } else {
        body.push(`  ${colors.dim("│")} ${colors.cyan("▌")}`);
      }
    }
    return [header, ...body];
  }
}

class UserBlock implements TranscriptBlock {
  private text = "";

  update(value: unknown): void {
    this.text = String(value);
  }

  invalidate(): void {}

  render(width: number): string[] {
    const prefix = `  ${colors.cyan(colors.bold("You"))}  `;
    const indent = " ".repeat(7);
    const body = new Text(this.text, 0, 0).render(Math.max(1, width - 7));
    return body.map((line, index) => `${index === 0 ? prefix : indent}${line}`);
  }
}

class ThinkingBlock implements TranscriptBlock {
  private text = "";
  private active = false;
  private expanded = false;

  update(value: unknown): void {
    const next = value as { text: string; active: boolean };
    if (this.active && !next.active) {
      this.expanded = false;
    }
    this.text = next.text;
    this.active = next.active;
  }

  toggle(): boolean {
    if (this.active) return false;
    this.expanded = !this.expanded;
    return true;
  }

  get isExpanded(): boolean {
    return this.expanded;
  }

  get isActive(): boolean {
    return this.active;
  }

  get preview(): string {
    return this.text.replace(/\s+/g, " ").trim();
  }

  invalidate(): void {}

  render(width: number): string[] {
    const state = this.active ? "thinking" : this.expanded ? "expanded" : "collapsed";
    const hint = this.active
      ? ""
      : this.expanded
        ? " · Ctrl+T collapse"
        : " · Ctrl+T inspect";
    const header = new Text(
      colors.dim(`  ├─ Thinking · ${state}${hint}`),
      0,
      0,
    ).render(width);
    if (!this.active && !this.expanded) {
      return header;
    }
    return [
      ...header,
      ...new Text(colors.dim(this.text), 5, 0).render(width),
    ];
  }
}

class ToolBlock implements TranscriptBlock {
  private tool: StreamingTool = {
    tool_call_id: "",
    tool_name: "tool",
    summary: "",
    status: "started",
  };

  update(value: unknown): void {
    this.tool = value as StreamingTool;
  }

  invalidate(): void {}

  render(width: number): string[] {
    const marker =
      this.tool.status === "completed"
        ? colors.green("✓")
        : this.tool.status === "failed" || this.tool.status === "denied"
          ? colors.red("✗")
          : colors.yellow("◉");
    const summary = cleanToolSummary(this.tool.tool_name, this.tool.summary);
    const detail = summary ? ` · ${colors.dim(summary)}` : "";
    return new Text(
      `  ├─ ${marker} ${colors.yellow(this.tool.tool_name)}${detail} ${colors.dim(`[${this.tool.status}]`)}`,
      0,
      0,
    ).render(width);
  }
}

class TextBlock implements TranscriptBlock {
  private readonly text = new Text("", 0, 0);
  private readonly style: (text: string) => string;

  constructor(style: (text: string) => string = colors.id) {
    this.style = style;
  }

  update(value: unknown): void {
    this.text.setText(this.style(String(value)));
  }

  invalidate(): void {
    this.text.invalidate();
  }

  render(width: number): string[] {
    return this.text.render(width);
  }
}

/** Reconciles transcript items by stable protocol and stream identifiers. */
export class TranscriptView implements Component {
  private readonly blocks = new Map<string, TranscriptBlock>();
  private order: string[] = [];
  private lastWidth = 80;

  setView(view: SessionViewState): void {
    const nextOrder: string[] = [];
    for (const item of view.snapshot?.transcript ?? []) {
      this.reconcileTranscriptItem(item, nextOrder);
    }
    for (const [id, buffer] of Object.entries(view.assistantBuffers)) {
      this.upsert(
        `assistant:${id}`,
        "assistant",
        { text: buffer, streaming: true },
        nextOrder,
      );
    }
    for (const [id, buffer] of Object.entries(view.thinkingBuffers)) {
      this.upsert(
        `thinking:${id}`,
        "thinking",
        { text: buffer, active: true },
        nextOrder,
      );
    }
    for (const tool of Object.values(view.tools)) {
      this.upsert(`tool:${tool.tool_call_id}`, "tool", tool, nextOrder);
    }
    if (view.error) {
      this.upsert(
        `error:${view.error.code}`,
        "error",
        `${view.error.code}: ${view.error.message}`,
        nextOrder,
      );
    }

    const retained = new Set(nextOrder);
    for (const key of this.blocks.keys()) {
      if (!retained.has(key)) {
        this.blocks.delete(key);
      }
    }
    this.order = nextOrder;
  }

  clear(): void {
    this.blocks.clear();
    this.order = [];
  }

  toggleThinking(id: string): boolean {
    const block = this.blocks.get(`thinking:${id}`);
    return block instanceof ThinkingBlock ? block.toggle() : false;
  }

  collapseExpandedThinking(): boolean {
    let collapsed = false;
    for (const key of this.order) {
      const block = this.blocks.get(key);
      if (block instanceof ThinkingBlock && block.isExpanded) {
        block.toggle();
        collapsed = true;
      }
    }
    return collapsed;
  }

  thinkingChoices(): ThinkingChoice[] {
    const choices: ThinkingChoice[] = [];
    let ordinal = 0;
    for (const key of this.order) {
      const block = this.blocks.get(key);
      if (!(block instanceof ThinkingBlock) || block.isActive) {
        continue;
      }
      ordinal += 1;
      choices.push({
        id: key.slice("thinking:".length),
        label: `Thinking ${ordinal}`,
        description: block.preview || "(no displayable reasoning)",
      });
    }
    return choices.reverse();
  }

  thinkingOffset(id: string): number | null {
    const target = `thinking:${id}`;
    let offset = 0;
    for (const key of this.order) {
      const block = this.blocks.get(key);
      if (!block) continue;
      if (key === target) return offset;
      if (offset > 0 && key.startsWith("user:")) offset += 1;
      offset += block.render(this.lastWidth).length;
    }
    return null;
  }

  /** Stable identity probe used by focused reconciliation tests. */
  componentForKey(key: string): Component | undefined {
    return this.blocks.get(key);
  }

  invalidate(): void {
    for (const block of this.blocks.values()) {
      block.invalidate?.();
    }
  }

  render(width: number): string[] {
    this.lastWidth = width;
    if (this.order.length === 0) {
      return new Text(
        `${colors.dim("No messages yet.")} ${colors.cyan("Type a request")} ${colors.dim("or use /resume.")}`,
        2,
        0,
      ).render(width);
    }
    const output: string[] = [];
    for (const key of this.order) {
      const block = this.blocks.get(key);
      if (!block) continue;
      if (output.length > 0 && key.startsWith("user:")) output.push("");
      output.push(...block.render(width));
    }
    return output;
  }

  private reconcileTranscriptItem(
    item: TranscriptItem,
    nextOrder: string[],
  ): void {
    switch (item.type) {
      case "user_message":
        this.upsert(
          `user:${item.id}`,
          "user",
          item.text,
          nextOrder,
        );
        break;
      case "assistant_message":
        this.upsert(`assistant:${item.id}`, "assistant", item.text, nextOrder);
        break;
      case "thinking":
        this.upsert(
          `thinking:${item.id}`,
          "thinking",
          { text: item.text, active: false },
          nextOrder,
        );
        break;
      case "tool_call":
        this.upsert(
          `tool:${item.id}`,
          "tool",
          {
            tool_call_id: item.id,
            tool_name: item.tool_name,
            summary: item.summary,
            status: item.status,
          } satisfies StreamingTool,
          nextOrder,
        );
        break;
      case "tool_result":
        this.upsert(
          `tool-result:${item.id}`,
          item.ok ? "success" : "error",
          `${item.ok ? "Tool result" : "Tool failed"} · ${item.summary}${item.truncated ? " · truncated" : ""}`,
          nextOrder,
        );
        break;
      case "system_notice":
        this.upsert(`notice:${item.id}`, "notice", item.text, nextOrder);
        break;
    }
  }

  private upsert(
    key: string,
    kind:
      | "assistant"
      | "thinking"
      | "tool"
      | "user"
      | "success"
      | "error"
      | "notice",
    value: unknown,
    nextOrder: string[],
  ): void {
    let block = this.blocks.get(key);
    if (!block) {
      block =
        kind === "assistant"
          ? new AssistantBlock()
          : kind === "user"
            ? new UserBlock()
            : kind === "thinking"
              ? new ThinkingBlock()
              : kind === "tool"
                ? new ToolBlock()
                : new TextBlock(
                    kind === "success"
                      ? (text) => `  ${colors.green("✓")} ${colors.green(text)}`
                      : kind === "error"
                        ? (text) => `  ${colors.red("✗")} ${colors.red(text)}`
                        : (text) => `  ${colors.dim("·")} ${colors.dim(text)}`,
                  );
      this.blocks.set(key, block);
    }
    block.update(value);
    nextOrder.push(key);
  }
}

function cleanToolSummary(toolName: string, summary: string): string {
  const clean = summary.trim();
  return clean.replace(/:$/, "").trim().toLowerCase() === toolName.trim().toLowerCase()
    ? ""
    : clean;
}
