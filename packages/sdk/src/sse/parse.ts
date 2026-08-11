/** Incremental SSE frame parser (transport-neutral). */

export interface SseFrame {
  id?: string | undefined;
  event?: string | undefined;
  data: string;
}

export class SseParser {
  #buffer = "";

  push(chunk: string): SseFrame[] {
    this.#buffer += chunk;
    const frames: SseFrame[] = [];
    // Normalize newlines
    let buf = this.#buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const frame = parseBlock(raw);
      if (frame) {
        frames.push(frame);
      }
    }
    this.#buffer = buf;
    return frames;
  }

  reset(): void {
    this.#buffer = "";
  }
}

function parseBlock(block: string): SseFrame | null {
  const lines = block.split("\n");
  let id: string | undefined;
  let event: string | undefined;
  const dataLines: string[] = [];
  let hasField = false;

  for (const line of lines) {
    if (!line || line.startsWith(":")) {
      continue;
    }
    hasField = true;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) {
      value = value.slice(1);
    }
    switch (field) {
      case "id":
        id = value;
        break;
      case "event":
        event = value;
        break;
      case "data":
        dataLines.push(value);
        break;
      default:
        break;
    }
  }

  if (!hasField || dataLines.length === 0) {
    return null;
  }
  return { id, event, data: dataLines.join("\n") };
}
