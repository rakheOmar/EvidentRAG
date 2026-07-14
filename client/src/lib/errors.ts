export type ErrorPresentation = "toast" | "inline" | "dialog";

import { logger } from "@/lib/logger";

export interface ErrorEnvelope {
  error?: {
    code?: string;
    details?: Record<string, unknown>;
    message?: string;
    request_id?: string | null;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly presentation: ErrorPresentation;
  readonly requestId: string | null;
  readonly status: number;

  constructor(
    message: string,
    status: number,
    options: {
      code?: string;
      details?: Record<string, unknown>;
      requestId?: string | null;
    } = {}
  ) {
    super(message);
    this.name = "ApiError";
    this.code = options.code ?? "request_failed";
    this.details = options.details ?? {};
    this.presentation = classifyError(status);
    this.requestId = options.requestId ?? null;
    this.status = status;
  }
}

export function classifyError(status: number): ErrorPresentation {
  if (status === 0) {
    return "dialog";
  }
  if (status === 400 || status === 422) {
    return "inline";
  }
  if (status >= 500 || status === 401 || status === 403) {
    return "dialog";
  }
  return "toast";
}

export function asAppError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }
  if (error instanceof TypeError) {
    return new ApiError(
      "We could not reach EvidentRAG. Check your connection.",
      0,
      {
        code: "network_error",
      }
    );
  }
  return new ApiError(
    error instanceof Error ? error.message : "Something went wrong.",
    500
  );
}

export function requestJson<T>(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<T> {
  return request(input, init, (response) => response.json() as Promise<T>);
}

export async function requestEmpty(
  input: RequestInfo | URL,
  init?: RequestInit
): Promise<void> {
  await request(input, init, async () => undefined);
}

async function request<T>(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  parseResponse: (response: Response) => Promise<T>
): Promise<T> {
  const startedAt = performance.now();
  const method = init?.method ?? "GET";
  const path = typeof input === "string" ? input : input.toString();
  const requestId = crypto.randomUUID();
  const wideEvent: Record<string, unknown> = {
    event: "api_request_completed",
    http_method: method,
    http_path: path,
    request_id: requestId,
  };

  try {
    const headers = new Headers(init?.headers);
    headers.set("x-request-id", requestId);
    const response = await fetch(input, { ...init, headers });

    wideEvent.http_status_code = response.status;
    if (!response.ok) {
      let body: ErrorEnvelope = {};
      try {
        body = (await response.json()) as ErrorEnvelope;
      } catch {
        // Keep the status-derived error when the server returned no JSON body.
      }
      const error = new ApiError(
        body.error?.message ??
          `${response.status} ${response.statusText || statusLabel(response.status)}`,
        response.status,
        {
          code: body.error?.code,
          details: body.error?.details,
          requestId: body.error?.request_id,
        }
      );
      wideEvent.outcome = "error";
      wideEvent.error = { code: error.code, type: error.name };
      throw error;
    }
    wideEvent.outcome = "success";
    return await parseResponse(response);
  } catch (unknownError) {
    const error = asAppError(unknownError);
    wideEvent.outcome = "error";
    wideEvent.error ??= { code: error.code, type: error.name };
    throw error;
  } finally {
    wideEvent.duration_ms = Math.round(performance.now() - startedAt);
    logger.info(wideEvent);
  }
}

function statusLabel(status: number): string {
  return (
    {
      400: "Bad Request",
      401: "Unauthorized",
      403: "Forbidden",
      404: "Not Found",
      409: "Conflict",
      422: "Unprocessable Entity",
      500: "Internal Server Error",
      503: "Service Unavailable",
    }[status] ?? "Request Failed"
  );
}
