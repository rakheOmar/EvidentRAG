import { afterEach, describe, expect, it, vi } from "vitest";

import type {
	DocumentRecord,
	ThreadDetail,
	ThreadSummary,
	ThreadTurnResponse,
} from "@/lib/types";

import {
	appendThreadMessage,
	createThread,
	deleteDocument,
	fetchDocuments,
	fetchModelContext,
	fetchThread,
	fetchThreads,
	putSentenceTraceFeedback,
	uploadDocument,
} from "../api";

const API_PREFIX = "/api/v1";
const REQUEST_ID_PATTERN = /^[0-9a-f-]{36}$/;

function makeThreadSummary(
	overrides: Partial<ThreadSummary> = {},
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

function makeThreadDetail(overrides: Partial<ThreadDetail> = {}): ThreadDetail {
	return { ...makeThreadSummary(), messages: [], ...overrides };
}

function makeTurnResponse(
	overrides: Partial<ThreadTurnResponse> = {},
): ThreadTurnResponse {
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
		...overrides,
	};
}

function makeDocument(overrides: Partial<DocumentRecord> = {}): DocumentRecord {
	return {
		byte_size: 512,
		created_at: "2026-07-11T10:00:00Z",
		document_id: "document-001",
		error_message: null,
		id: "document-001",
		is_current: false,
		original_filename: "handbook.pdf",
		page_count: 0,
		source_id: "source-001",
		source_key: "source-key",
		status: "queued",
		title: "handbook",
		updated_at: "2026-07-11T10:00:00Z",
		version_number: 1,
		warnings: [],
		...overrides,
	};
}

function jsonResponse(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		headers: { "Content-Type": "application/json" },
		status,
	});
}

function getFirstCall(fetchMock: ReturnType<typeof vi.fn>) {
	const [firstCall] = fetchMock.mock.calls;
	if (!firstCall) {
		throw new Error("Expected fetch to be called at least once.");
	}
	return firstCall;
}

function stubFetch(response: Response | Response[]) {
	const fetchMock = vi.fn();
	for (const item of Array.isArray(response) ? response : [response]) {
		fetchMock.mockResolvedValueOnce(item);
	}
	vi.stubGlobal("fetch", fetchMock);
	return fetchMock;
}

afterEach(() => {
	vi.unstubAllGlobals();
});

describe("thread API wrappers", () => {
	it.each([
		{
			call: () => createThread("What is RAG?"),
			expectedBody: { content: "What is RAG?" },
			expectedPath: `${API_PREFIX}/threads`,
			label: "creates a thread",
		},
		{
			call: () => appendThreadMessage("thread-001", "And what about HNSW?"),
			expectedBody: { content: "And what about HNSW?" },
			expectedPath: `${API_PREFIX}/threads/thread-001/messages`,
			label: "appends a thread message",
		},
	])("$label", async ({ call, expectedPath, expectedBody }) => {
		const expected = makeTurnResponse();
		const fetchMock = stubFetch(jsonResponse(expected, 201));

		await expect(call()).resolves.toEqual(expected);

		expect(fetchMock).toHaveBeenCalledTimes(1);
		const [url, init] = getFirstCall(fetchMock);
		expect(url).toBe(expectedPath);
		expect(init?.method).toBe("POST");
		expect(JSON.parse(init?.body as string)).toEqual(expectedBody);
		expect(new Headers(init?.headers).get("x-request-id")).toMatch(
			REQUEST_ID_PATTERN,
		);
	});

	it.each([
		{
			expected: "400 Bad Request",
			presentation: "inline",
			status: 400,
			statusText: "Bad Request",
		},
		{
			expected: "404 Not Found",
			presentation: "toast",
			status: 404,
			statusText: "Not Found",
		},
		{
			expected: "503 Service Unavailable",
			presentation: "dialog",
			status: 503,
			statusText: "Service Unavailable",
		},
	])("maps a $status response to an ApiError", async ({
		expected,
		presentation,
		status,
		statusText,
	}) => {
		stubFetch(new Response("", { status, statusText }));

		await expect(createThread("oops")).rejects.toMatchObject({
			message: expected,
			presentation,
			status,
		});
	});
});

describe("thread and model read wrappers", () => {
	it.each([
		{
			body: [makeThreadSummary({ id: "thread-1", title: "first" })],
			call: () => fetchThreads(),
			label: "lists threads",
			path: `${API_PREFIX}/threads`,
		},
		{
			body: makeThreadDetail({ id: "thread-001" }),
			call: () => fetchThread("thread-001"),
			label: "fetches one thread",
			path: `${API_PREFIX}/threads/thread-001`,
		},
		{
			body: { context_window: 8192, generation_model: "gpt-4.1-mini" },
			call: () => fetchModelContext(),
			label: "fetches model context",
			path: `${API_PREFIX}/model-context`,
		},
	])("$label", async ({ call, path, body }) => {
		const fetchMock = stubFetch(jsonResponse(body));

		await expect(call()).resolves.toEqual(body);

		expect(fetchMock).toHaveBeenCalledTimes(1);
		const [url, init] = getFirstCall(fetchMock);
		expect(url).toBe(path);
		expect(init?.method).toBe("GET");
	});
});

describe("feedback API", () => {
	it.each([
		["up", { rating: "up", trace_id: "trace-001" }],
		["down", { rating: "down", trace_id: "trace-001" }],
	] as const)("PUTs a %s rating", async (rating, expected) => {
		const fetchMock = stubFetch(jsonResponse(expected));

		await expect(
			putSentenceTraceFeedback("trace-001", rating),
		).resolves.toEqual(expected);

		const [url, init] = getFirstCall(fetchMock);
		expect(url).toBe(`${API_PREFIX}/sentence-traces/trace-001/rating`);
		expect(init?.method).toBe("PUT");
		expect(JSON.parse(init?.body as string)).toEqual({ rating });
	});
});

describe("document API wrappers", () => {
	it.each([
		{ expectedSourceKey: null, sourceKey: undefined },
		{ expectedSourceKey: "source-override", sourceKey: "source-override" },
	])("uploads a PDF and handles source_key=$sourceKey", async ({
		expectedSourceKey,
		sourceKey,
	}) => {
		const expected = makeDocument();
		const fetchMock = stubFetch(jsonResponse(expected, 201));
		const file = new File(["%PDF-1.7"], "handbook.pdf", {
			type: "application/pdf",
		});

		await expect(uploadDocument(file, sourceKey)).resolves.toEqual(expected);

		const [url, init] = getFirstCall(fetchMock);
		expect(url).toBe(`${API_PREFIX}/documents`);
		expect(init?.method).toBe("POST");
		expect(init?.body).toBeInstanceOf(FormData);
		const body = init?.body as FormData;
		expect(body.get("file")).toBe(file);
		expect(body.get("source_key")).toBe(expectedSourceKey);
	});

	it("lists documents and deletes without parsing a 204 body", async () => {
		const listResponse = { items: [], limit: 100, offset: 0, total: 0 };
		const fetchMock = stubFetch([
			jsonResponse(listResponse),
			new Response(null, { status: 204 }),
		]);

		await expect(fetchDocuments()).resolves.toEqual(listResponse);
		await expect(deleteDocument("document-001")).resolves.toBeUndefined();

		expect(fetchMock.mock.calls[1]?.[0]).toBe(
			`${API_PREFIX}/documents/document-001`,
		);
		expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("DELETE");
	});
});
