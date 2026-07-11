import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  ThreadDetail,
  ThreadSummary,
  ThreadTurnResponse,
} from "@/lib/types";

import {
  appendThreadMessage,
  createThread,
  fetchThread,
  fetchThreads,
  putSentenceTraceFeedback,
} from "../api";

const createThreadErrorMessage = /400 Bad Request/;

function makeThreadSummary(
  overrides: Partial<ThreadSummary> = {}
): ThreadSummary {
  return {
    created_at: "2026-07-04T10:00:00Z",
    id: "thread-001",
    summary: "A conversation about RAG.",
    title: "RAG basics",
    updated_at: "2026-07-04T10:00:00Z",
    ...overrides,
  };
}

function makeTurnResponse(): ThreadTurnResponse {
  return {
    assistant_message: {
      completed_at: null,
      content_text: "",
      created_at: "2026-07-04T10:00:01Z",
      error_message: null,
      id: "msg-assistant-1",
      position: 1,
      reply_to_message_id: "msg-user-1",
      role: "assistant",
      selected_route: null,
      status: "pending",
      sub_queries: [],
      thread_id: "thread-001",
      updated_at: "2026-07-04T10:00:01Z",
    },
    thread: makeThreadSummary(),
    user_message: {
      completed_at: "2026-07-04T10:00:00Z",
      content_text: "What is RAG?",
      created_at: "2026-07-04T10:00:00Z",
      error_message: null,
      id: "msg-user-1",
      position: 0,
      reply_to_message_id: null,
      role: "user",
      selected_route: null,
      status: "completed",
      sub_queries: [],
      thread_id: "thread-001",
      updated_at: "2026-07-04T10:00:00Z",
    },
  };
}

function makeThreadDetail(overrides: Partial<ThreadDetail> = {}): ThreadDetail {
  return {
    ...makeThreadSummary(),
    messages: [],
    ...overrides,
  };
}

function stubJson(body: unknown, init: { status?: number } = {}): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status: 200,
    ...init,
  });
}

function getFirstCall(fetchMock: ReturnType<typeof vi.fn>) {
  const [firstCall] = fetchMock.mock.calls;

  if (firstCall === undefined) {
    throw new Error("Expected fetch to be called at least once.");
  }

  return firstCall;
}

describe("createThread", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs { content } to /api/v1/threads and returns the parsed ThreadTurnResponse", async () => {
    const expected = makeTurnResponse();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(expected), {
        headers: { "Content-Type": "application/json" },
        status: 201,
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await createThread("What is RAG?");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/threads");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      content: "What is RAG?",
    });
    expect(result).toEqual(expected);
  });

  it("throws a meaningful error on a 4xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Bad Request", { status: 400 }))
    );

    await expect(createThread("oops")).rejects.toThrowError(
      createThreadErrorMessage
    );
  });
});

describe("appendThreadMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs to /api/v1/threads/{id}/messages", async () => {
    const expected = makeTurnResponse();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(stubJson(expected, { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await appendThreadMessage(
      "thread-001",
      "And what about HNSW?"
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/threads/thread-001/messages");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({
      content: "And what about HNSW?",
    });
    expect(result).toEqual(expected);
  });
});

describe("fetchThreads", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GETs /api/v1/threads and returns the parsed ThreadSummary[]", async () => {
    const expected = [
      makeThreadSummary({ id: "thread-1", title: "first" }),
      makeThreadSummary({ id: "thread-2", title: "second" }),
    ];
    const fetchMock = vi.fn().mockResolvedValue(stubJson(expected));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchThreads();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/threads");
    expect(init?.method).toBe("GET");
    expect(result).toEqual(expected);
  });
});

describe("fetchThread", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GETs /api/v1/threads/{id} and returns the parsed ThreadDetail", async () => {
    const expected = makeThreadDetail({
      id: "thread-001",
      messages: [
        makeTurnResponse().user_message,
        makeTurnResponse().assistant_message,
      ],
    });
    const fetchMock = vi.fn().mockResolvedValue(stubJson(expected));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchThread("thread-001");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/threads/thread-001");
    expect(init?.method).toBe("GET");
    expect(result).toEqual(expected);
  });
});

describe("putSentenceTraceFeedback", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("PUTs the rating to /api/v1/sentence-traces/{id}/rating", async () => {
    const expected = { rating: "up", trace_id: "trace-001" };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(stubJson(expected, { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await putSentenceTraceFeedback("trace-001", "up");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/sentence-traces/trace-001/rating");
    expect(init?.method).toBe("PUT");
    expect(JSON.parse(init?.body as string)).toEqual({ rating: "up" });
    expect(result).toEqual(expected);
  });
});
