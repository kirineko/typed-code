import { PROTOCOL_VERSION } from "../version.js";
import { TypedCodeError } from "./errors.js";
import type { StructuredError } from "../types/protocol.js";

export type FetchLike = typeof fetch;

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
  auth?: boolean;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  accept?: string;
}

export async function apiRequest(
  fetchImpl: FetchLike,
  baseUrl: string,
  token: string,
  path: string,
  options: RequestOptions = {},
): Promise<Response> {
  const url = new URL(path.startsWith("http") ? path : `${baseUrl}${path}`);
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const headers: Record<string, string> = {
    "X-Typed-Code-Protocol": String(PROTOCOL_VERSION),
    Accept: options.accept ?? "application/json",
    ...options.headers,
  };
  if (options.auth !== false) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    const init: RequestInit = {
      method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
      headers,
    };
    if (options.body !== undefined) {
      init.body = JSON.stringify(options.body);
    }
    if (options.signal) {
      init.signal = options.signal;
    }
    response = await fetchImpl(url, init);
  } catch (cause) {
    throw new TypedCodeError("network request failed", {
      code: "network_error",
      cause,
    });
  }

  return response;
}

export async function readJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  let parsed: unknown;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch (cause) {
    throw new TypedCodeError("response is not valid JSON", {
      code: "protocol_mismatch",
      status: response.status,
      cause,
    });
  }

  if (!response.ok) {
    const errBody = parsed as { error?: StructuredError } | null;
    if (errBody?.error && typeof errBody.error.message === "string") {
      throw TypedCodeError.fromStructured(errBody.error, response.status);
    }
    throw new TypedCodeError(
      `request failed with status ${response.status}`,
      { code: "internal_error", status: response.status },
    );
  }

  return parsed as T;
}
