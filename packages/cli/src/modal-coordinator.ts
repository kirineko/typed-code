import type {
  Component,
  OverlayHandle,
  OverlayOptions,
  TUI,
} from "@earendil-works/pi-tui";

/**
 * Keep action surfaces below the fixed header instead of obscuring the active
 * response in the center of the transcript.
 */
export function actionOverlayOptions(options: OverlayOptions = {}): OverlayOptions {
  return {
    anchor: "top-center",
    offsetY: 1,
    margin: { top: 1, right: 2, bottom: 3, left: 2 },
    ...options,
  };
}

export class ModalCoordinator {
  private readonly tui: TUI;
  private handle: OverlayHandle | null = null;
  private returnFocus: Component | null = null;

  constructor(tui: TUI) {
    this.tui = tui;
  }

  get isOpen(): boolean {
    return this.handle !== null;
  }

  show(
    component: Component,
    returnFocus: Component | null,
    options: OverlayOptions = {},
  ): OverlayHandle {
    this.close();
    this.returnFocus = returnFocus;
    this.handle = this.tui.showOverlay(component, actionOverlayOptions(options));
    this.handle.focus();
    this.tui.requestRender();
    return this.handle;
  }

  close(): void {
    const handle = this.handle;
    if (!handle) return;
    const target = this.returnFocus;
    handle.unfocus({ target });
    handle.hide();
    this.handle = null;
    this.returnFocus = null;
    this.tui.setFocus(target);
    this.tui.requestRender();
  }
}
