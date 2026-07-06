import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnswerDetail, QuerySummary } from "@/lib/types";

import { fetchAnswer, fetchQueryHistory, postQuery } from "../api";

const postQueryErrorMessage = /POST \/api\/v1\/queries failed: 400/;

function makeQuerySummary(overrides: Partial<QuerySummary> = {}): QuerySummary {
  return {
    id: "q-001",
    query_text: "What is RAG?",
    selected_route: "simple",
    status: "pending",
    error_message: null,
    created_at: "2026-07-04T10:00:00Z",
    updated_at: "2026-07-04T10:00:00Z",
    completed_at: null,
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
  const firstCall = fetchMock.mock.calls[0];

  if (firstCall === undefined) {
    throw new Error("Expected fetch to be called at least once.");
  }

  return firstCall;
}

describe("postQuery", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs { query_text } to /api/v1/queries and returns the parsed QuerySummary", async () => {
    const expected = makeQuerySummary();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(expected), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await postQuery("What is RAG?");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/queries");
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({ "Content-Type": "application/json" });
    expect(JSON.parse(init?.body as string)).toEqual({
      query_text: "What is RAG?",
    });
    expect(result).toEqual(expected);
  });

  it("throws a meaningful error on a 4xx response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("Bad Request", { status: 400 }))
    );

    await expect(postQuery("oops")).rejects.toThrowError(postQueryErrorMessage);
  });
});

describe("fetchQueryHistory", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GETs /api/v1/queries and returns the parsed QuerySummary[]", async () => {
    const expected = [
      makeQuerySummary({ id: "q-1", query_text: "first", status: "completed" }),
      makeQuerySummary({ id: "q-2", query_text: "second", status: "running" }),
    ];
    const fetchMock = vi.fn().mockResolvedValue(stubJson(expected));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchQueryHistory();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/queries");
    expect(init?.method).toBe("GET");
    expect(result).toEqual(expected);
  });
});

describe("fetchAnswer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GETs /api/v1/queries/{id}/answer and parses deeply nested segments + evidence", async () => {
    const expected: AnswerDetail = {
      id: "a-001",
      query_id: "q-001",
      full_text: "Cats purr. Dogs bark.",
      segments: [
        {
          segment_index: 0,
          text: "Cats purr.",
          evidence_ids: ["e-1", "e-2"],
        },
        {
          segment_index: 1,
          text: "Dogs bark.",
          evidence_ids: ["e-3"],
        },
      ],
      evidence: [
        {
          id: "e-1",
          content: "Cats purr when content.",
          context_header: "Felis catus",
          document_title: "Feline Behaviour",
          document_slug: "feline-behaviour",
          page: 12,
        },
        {
          id: "e-2",
          content: "Purring ranges from 25-150 Hz.",
          context_header: null,
          document_title: null,
          document_slug: null,
          page: null,
        },
        {
          id: "e-3",
          content: "Dogs bark to communicate.",
          context_header: "Canis familiaris",
          document_title: "Canine Behaviour",
          document_slug: "canine-behaviour",
          page: 33,
        },
      ],
    };
    const fetchMock = vi.fn().mockResolvedValue(stubJson(expected));
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchAnswer("q-001");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = getFirstCall(fetchMock);
    expect(url).toBe("/api/v1/queries/q-001/answer");
    expect(init?.method).toBe("GET");
    expect(result).toEqual(expected);
  });
});
