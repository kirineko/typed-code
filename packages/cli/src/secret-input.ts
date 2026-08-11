import {
  Input,
  type Component,
  type Focusable,
} from "@earendil-works/pi-tui";

/** Single-line input that keeps the real value but renders only fixed-width masks. */
export class SecretInput extends Input {
  override render(width: number): string[] {
    const secret = this.getValue();
    this.setValue("*".repeat(secret.length));
    try {
      return super.render(width);
    } finally {
      this.setValue(secret);
    }
  }
}

export class SecretPrompt implements Component, Focusable {
  focused = false;
  private readonly input = new SecretInput();
  private readonly label: string;

  constructor(
    label: string,
    onSubmit: (value: string) => void,
    onEscape: () => void,
  ) {
    this.label = label;
    this.input.onSubmit = onSubmit;
    this.input.onEscape = onEscape;
  }

  clear(): void {
    this.input.setValue("");
  }

  handleInput(data: string): void {
    this.input.focused = this.focused;
    this.input.handleInput(data);
  }

  render(width: number): string[] {
    this.input.focused = this.focused;
    return [this.label, ...this.input.render(width)];
  }

  invalidate(): void {
    this.input.invalidate();
  }
}
