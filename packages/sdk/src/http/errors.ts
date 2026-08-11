import type { ErrorCode, StructuredError } from "../types/protocol.js";

export class TypedCodeError extends Error {
  readonly code: ErrorCode | string;
  readonly status: number | null;
  readonly details: Record<string, unknown> | null;

  constructor(
    message: string,
    opts: {
      code?: ErrorCode | string;
      status?: number | null;
      details?: Record<string, unknown> | null;
      cause?: unknown;
    } = {},
  ) {
    super(message);
    this.name = "TypedCodeError";
    this.code = opts.code ?? "internal_error";
    this.status = opts.status ?? null;
    this.details = opts.details ?? null;
    if (opts.cause !== undefined) {
      (this as Error & { cause?: unknown }).cause = opts.cause;
    }
  }

  static fromStructured(
    error: StructuredError,
    status: number | null = null,
  ): TypedCodeError {
    return new TypedCodeError(error.message, {
      code: error.code,
      status,
      details: error.details ?? null,
    });
  }
}
