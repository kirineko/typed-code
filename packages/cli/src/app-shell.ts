import {
  Editor,
  ScrollView,
  TuiAltScreen,
  VStack,
} from "@earendil-works/pi-tui";

import {
  deriveAgentActivity,
  type ActivitySource,
  type AgentActivity,
} from "./activity.js";
import type { AppSessionState } from "./app-session.js";
import { ActivityBar } from "./components/activity-bar.js";
import { AppHeader } from "./components/app-header.js";
import { StatusFooter } from "./components/status-footer.js";
import { TranscriptView } from "./components/transcript-view.js";
import { ModalCoordinator } from "./modal-coordinator.js";

export class AppShell {
  readonly tui: TuiAltScreen;
  readonly editor: Editor;
  readonly transcript = new TranscriptView();
  readonly transcriptScroll: ScrollView;
  readonly header = new AppHeader();
  readonly activity = new ActivityBar();
  readonly footer = new StatusFooter();
  readonly modals: ModalCoordinator;
  private lastSequence = 0;
  private newOutput = false;
  private renderQueued = false;
  private currentActivity: AgentActivity = {
    kind: "ready",
    label: "Ready",
    connection: "idle",
  };

  constructor(tui: TuiAltScreen, editor: Editor) {
    this.tui = tui;
    this.editor = editor;
    this.transcriptScroll = new ScrollView(this.transcript, {
      follow: "end",
      primary: true,
      overscroll: "chain",
      scrollbar: "auto",
    });
    this.modals = new ModalCoordinator(tui);
    tui.setLayoutRoot(
      new VStack([
        { component: this.header, basis: "auto", minSize: 1 },
        {
          component: this.transcriptScroll,
          basis: 0,
          grow: 1,
          shrink: 1,
          minSize: 1,
        },
        { component: this.activity, basis: "auto", minSize: 1 },
        { component: editor, basis: "auto", shrink: 1, minSize: 1 },
        { component: this.footer, basis: "auto", minSize: 1 },
      ]),
    );
    tui.setFocus(editor);
  }

  sync(state: AppSessionState, options: { cancelling?: boolean } = {}): void {
    if (state.kind === "attached") {
      const view = state.controller.view;
      if (
        view.lastSequence > this.lastSequence &&
        !this.transcriptScroll.isFollowingEnd
      ) {
        this.newOutput = true;
      }
      this.lastSequence = view.lastSequence;
      this.transcript.setView(view);
    } else {
      this.lastSequence = 0;
      this.newOutput = false;
      this.transcript.clear();
    }

    this.header.setState(state);
    const source: ActivitySource =
      state.kind === "attached"
        ? { kind: "attached", view: state.controller.view }
        : { kind: state.kind };
    this.currentActivity = deriveAgentActivity(source, options);
    this.activity.setActivity(this.currentActivity, this.newOutput);
    this.footer.setState(state);
    this.editor.disableSubmit =
      state.kind === "creating" ||
      (state.kind === "attached" && state.controller.view.phase !== "idle");
    this.requestRender();
  }

  scrollToEnd(): void {
    this.transcriptScroll.scrollToEnd();
    this.newOutput = false;
    this.activity.setActivity(this.currentActivity, false);
    this.requestRender();
  }
  collapseExpandedThinking(): boolean {
    const collapsed = this.transcript.collapseExpandedThinking();
    if (collapsed) this.requestRender();
    return collapsed;
  }

  toggleThinking(id: string): boolean {
    const toggled = this.transcript.toggleThinking(id);
    if (!toggled) return false;
    const offset = this.transcript.thinkingOffset(id);
    if (offset !== null) this.transcriptScroll.scrollTo(Math.max(0, offset - 1));
    this.requestRender();
    return true;
  }

  flash(message: string, durationMs = 2400): void {
    this.tui.flash(message, durationMs);
  }

  requestRender(): void {
    if (this.renderQueued) return;
    this.renderQueued = true;
    queueMicrotask(() => {
      this.renderQueued = false;
      this.tui.requestRender();
    });
  }
}
