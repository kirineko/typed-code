import { apiRequest, type FetchLike } from "../http/fetch.js";
import { TypedCodeError } from "../http/errors.js";
import { parseEventEnvelope, type EventEnvelope } from "../types/events.js";
import type { SessionSnapshot } from "../types/protocol.js";
import { SseParser } from "./parse.js";

export interface StreamOptions {
  after?: number;
  signal?: AbortSignal;
  onEvent: (event: EventEnvelope) => void;
  onReset: (snapshot: SessionSnapshot) => void;
  onError?: (err: unknown) => void;
  onOpen?: () => void;
  backoffMs?: { initial: number; max: number };
}

export interface EventSubscription {
  readonly lastSequence: number;
  close(): void;
}

export function streamSessionEvents(
  fetchImpl: FetchLike,
  baseUrl: string,
  token: string,
  sessionId: string,
  options: StreamOptions,
): EventSubscription {
  const backoff = options.backoffMs ?? { initial: 250, max: 5000 };
  let lastSequence = options.after ?? 0;
  let closed = false;
  let attempt = 0;
  const ac = new AbortController();

  const onAbort = () => {
    closed = true;
    ac.abort();
  };
  options.signal?.addEventListener("abort", onAbort, { once: true });

  const run = async () => {
    while (!closed) {
      try {
        const response = await apiRequest(
          fetchImpl,
          baseUrl,
          token,
          `/v1/sessions/${encodeURIComponent(sessionId)}/events`,
          {
            auth: true,
            accept: "text/event-stream",
            query: { after: lastSequence },
            signal: ac.signal,
          },
        );

        if (!response.ok) {
          const text = await response.text();
          throw new TypedCodeError(
            `SSE request failed with status ${response.status}`,
            { code: "internal_error", status: response.status, details: { body: text } },
          );
        }
        if (!response.body) {
          throw new TypedCodeError("SSE response missing body", {
            code: "protocol_mismatch",
            status: response.status,
          });
        }
        options.onOpen?.();

        attempt = 0;
        const parser = new SseParser();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (!closed) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }
          const chunk = decoder.decode(value, { stream: true });
          const frames = parser.push(chunk);
          for (const frame of frames) {
            if (!frame.data) continue;
            let envelope: EventEnvelope;
            try {
              envelope = parseEventEnvelope(JSON.parse(frame.data));
            } catch (err) {
              options.onError?.(err);
              continue;
            }

            if (envelope.type === "replay.reset") {
              const data = envelope.data as { snapshot: SessionSnapshot };
              options.onReset(data.snapshot);
              lastSequence = data.snapshot.latest_event_sequence ?? lastSequence;
              // Server ends stream after reset; reconnect with new after.
              break;
            }

            if (envelope.sequence <= lastSequence) {
              continue;
            }
            if (envelope.sequence !== lastSequence + 1) {
              await reader.cancel();
              throw new TypedCodeError(
                `SSE sequence gap: expected ${lastSequence + 1}, received ${envelope.sequence}`,
                {
                  code: "protocol_mismatch",
                  status: response.status,
                  details: {
                    expected_sequence: lastSequence + 1,
                    received_sequence: envelope.sequence,
                  },
                },
              );
            }
            lastSequence = envelope.sequence;
            options.onEvent(envelope);
          }
        }
      } catch (err) {
        if (closed || ac.signal.aborted) {
          return;
        }
        options.onError?.(err);
      }

      if (closed || ac.signal.aborted) {
        return;
      }
      // Reconnect with backoff
      const delay = Math.min(
        backoff.max,
        backoff.initial * 2 ** Math.min(attempt, 6),
      );
      attempt += 1;
      await sleep(delay, ac.signal);
    }
  };

  void run();

  return {
    get lastSequence() {
      return lastSequence;
    },
    close() {
      closed = true;
      ac.abort();
      options.signal?.removeEventListener("abort", onAbort);
    },
  };
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) {
      resolve();
      return;
    }
    const t = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      resolve();
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });
}
