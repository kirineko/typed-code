import {
  Text,
  type Component,
  type Focusable,
  matchesKey,
} from "@earendil-works/pi-tui";

import { colors, panelFrame } from "../theme.js";

export class InfoDialog implements Component {
  private readonly title: string;
  private readonly body: string;
  private readonly onClose: () => void;

  constructor(title: string, body: string, onClose: () => void) {
    this.title = title;
    this.body = body;
    this.onClose = onClose;
  }

  invalidate(): void {}

  handleInput(data: string): void {
    if (matchesKey(data, "escape") || matchesKey(data, "enter")) {
      this.onClose();
    }
  }

  render(width: number): string[] {
    const panelWidth = Math.max(20, width);
    const innerWidth = Math.max(1, panelWidth - 4);
    return panelFrame(
      [
        ...new Text(colors.bold(this.title), 0, 0).render(innerWidth),
        "",
        ...new Text(this.body, 0, 0).render(innerWidth),
        "",
        ...new Text(colors.dim("Enter/Esc close"), 0, 0).render(innerWidth),
      ],
      panelWidth,
    );
  }
}

export class FramedDialog implements Component, Focusable {
  focused = false;
  private readonly title: string;
  private readonly detail: string;
  private readonly child: Component;

  constructor(title: string, detail: string, child: Component) {
    this.title = title;
    this.detail = detail;
    this.child = child;
  }

  invalidate(): void {
    this.child.invalidate();
  }

  handleInput(data: string): void {
    if ("focused" in this.child) {
      (this.child as Component & Focusable).focused = this.focused;
    }
    this.child.handleInput?.(data);
  }

  render(width: number): string[] {
    const panelWidth = Math.max(20, width);
    const innerWidth = Math.max(1, panelWidth - 4);
    if ("focused" in this.child) {
      (this.child as Component & Focusable).focused = this.focused;
    }
    return panelFrame(
      [
        ...new Text(colors.bold(this.title), 0, 0).render(innerWidth),
        ...new Text(colors.dim(this.detail), 0, 0).render(innerWidth),
        "",
        ...this.child.render(innerWidth),
      ],
      panelWidth,
    );
  }
}
