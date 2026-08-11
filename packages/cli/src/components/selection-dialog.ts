import {
  SelectList,
  Text,
  type Component,
  type SelectItem,
} from "@earendil-works/pi-tui";

import { colors, panelFrame, selectListTheme } from "../theme.js";

export class SelectionDialog implements Component {
  readonly list: SelectList;
  private readonly title: string;
  private readonly detail: string;

  constructor(
    title: string,
    detail: string,
    items: SelectItem[],
    maxVisible = 12,
  ) {
    this.title = title;
    this.detail = detail;
    this.list = new SelectList(items, maxVisible, selectListTheme);
  }

  invalidate(): void {
    this.list.invalidate();
  }

  handleInput(data: string): void {
    this.list.handleInput(data);
  }

  render(width: number): string[] {
    const panelWidth = Math.max(20, width);
    const innerWidth = Math.max(1, panelWidth - 4);
    return panelFrame(
      [
        colors.bold(this.title),
        colors.dim(this.detail),
        "",
        ...this.list.render(innerWidth),
      ],
      panelWidth,
    );
  }
}
