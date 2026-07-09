import type { AppendMessage, ExternalStoreAdapter } from "@assistant-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EvidentChatMessage, QuerySummary } from "@/lib/types";

import { useEvidentRuntime } from "../use-evident-runtime";

const fetchAnswerMock = vi.fn();
const postQueryMock = vi.fn();
const useExternalStoreRuntimeMock = vi.fn(
  (adapter: ExternalStoreAdapter<EvidentChatMessage>) => adapter
);
const useQueryHistoryMock = vi.fn<
  () => { data: QuerySummary[]; isLoading: boolean }
>(() => ({
  data: [],
  isLoading: false,
}));

vi.mock("@assistant-ui/react", () => ({
  useExternalStoreRuntime: (
    adapter: ExternalStoreAdapter<EvidentChatMessage>
  ) => useExternalStoreRuntimeMock(adapter),
}));

vi.mock("@/lib/api", () => ({
  fetchAnswer: (...args: unknown[]) => fetchAnswerMock(...args),
  postQuery: (...args: unknown[]) => postQueryMock(...args),
  queryKeys: { queries: ["queries"] },
  useQueryHistory: () => useQueryHistoryMock(),
}));

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  readonly close = vi.fn();
  readonly listeners = new Map<
    string,
    Set<(event: MessageEvent<string>) => void>
  >();
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(
    type: string,
    listener: (event: MessageEvent<string>) => void
  ) {
    const listeners =
      this.listeners.get(type) ??
      new Set<(event: MessageEvent<string>) => void>();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  emit(type: string, payload: unknown) {
    const event = new MessageEvent<string>(type, {
      data: JSON.stringify(payload),
    });

    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  emitTransportError() {
    const event = new Event("error") as MessageEvent<string>;

    for (const listener of this.listeners.get("error") ?? []) {
      listener(event);
    }
  }
}

function getFirstEventSource() {
  const eventSource = FakeEventSource.instances[0];

  if (eventSource === undefined) {
    throw new Error("Expected an EventSource instance to exist.");
  }

  return eventSource;
}

function makeAppendMessage(text: string): AppendMessage {
  return {
    attachments: [],
    content: [{ text, type: "text" }],
    createdAt: new Date("2026-07-04T10:00:00Z"),
    metadata: { custom: {} },
    parentId: null,
    role: "user",
    runConfig: undefined,
    sourceId: null,
  };
}

function createWrapper() {
  const queryClient = new QueryClient();

  return function Wrapper({ children }: PropsWithChildren) {
    return createElement(
      QueryClientProvider,
      { client: queryClient },
      children
    );
  };
}

describe("useEvidentRuntime", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    fetchAnswerMock.mockReset();
    postQueryMock.mockReset();
    useExternalStoreRuntimeMock.mockClear();
    useQueryHistoryMock.mockReset();
    useQueryHistoryMock.mockReturnValue({ data: [], isLoading: false });
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("streams content_parts events through completion", async () => {
    postQueryMock.mockResolvedValue({ id: "query-1" });
    fetchAnswerMock.mockResolvedValue({
      evidence: [],
      full_text: "Evidence Retrieval Memory improves future retrieval.",
      id: "answer-1",
      query_id: "query-1",
      segments: [],
    });

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(
        makeAppendMessage("How does Evidence Retrieval Memory work?")
      );
    });

    expect(postQueryMock).toHaveBeenCalledWith(
      "How does Evidence Retrieval Memory work?"
    );

    const eventSource = getFirstEventSource();
    expect(eventSource.url).toBe("/api/v1/queries/query-1/events");

    act(() => {
      eventSource.emit("route_selected", {
        route: "multi_hop",
        sub_queries: ["What is ERM?", "How does ERM improve retrieval?"],
      });
    });

    act(() => {
      eventSource.emit("hop_progress", {
        hop: 1,
        intermediate_answer: "ERM stores feedback-linked retrieval memory.",
        sub_query: "What is ERM?",
      });
    });

    act(() => {
      eventSource.emit("content_parts", {
        parts: [{ type: "reasoning", text: "Routing Query..." }],
      });
    });

    act(() => {
      eventSource.emit("content_parts", {
        parts: [
          { type: "reasoning", text: "Routing Query..." },
          { type: "text", text: "ERM" },
        ],
      });
    });

    act(() => {
      eventSource.emit("done", {
        query_id: "query-1",
        content_parts: [
          {
            type: "text",
            text: "Evidence Retrieval Memory improves future retrieval.",
          },
          {
            type: "source",
            sourceType: "document",
            id: "ev-1",
            title: "ERM Paper",
            mediaType: "text/plain",
          },
        ],
        error: false,
      });
    });

    await waitFor(() => {
      expect(result.current.isRunning).toBe(false);
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0]).toMatchObject({
        contentParts: [
          { type: "text", text: "How does Evidence Retrieval Memory work?" },
        ],
        role: "user",
      });
      expect(result.current.messages[1]).toMatchObject({
        contentParts: [
          {
            type: "text",
            text: "Evidence Retrieval Memory improves future retrieval.",
          },
        ],
        hopProgress: [
          {
            hop: 1,
            intermediate_answer: "ERM stores feedback-linked retrieval memory.",
            sub_query: "What is ERM?",
          },
        ],
        queryId: "query-1",
        role: "assistant",
        route: "multi_hop",
        status: "complete",
        subQueries: ["What is ERM?", "How does ERM improve retrieval?"],
      });
    });

    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });

  it("marks the assistant as error when done event has error flag", async () => {
    postQueryMock.mockResolvedValue({ id: "query-2" });

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("Break this Query"));
    });

    const eventSource = getFirstEventSource();

    act(() => {
      eventSource.emit("done", {
        query_id: "query-2",
        content_parts: [],
        error: true,
        error_message: "Worker exploded",
      });
    });

    await waitFor(() => {
      expect(result.current.isRunning).toBe(false);
      expect(result.current.messages[1]).toMatchObject({
        queryId: "query-2",
        role: "assistant",
        status: "error",
      });
    });

    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });

  it("marks the assistant as error when SSE stream transport fails", async () => {
    postQueryMock.mockResolvedValue({ id: "query-transport" });

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(
        makeAppendMessage("Explain citation transport failures")
      );
    });

    const eventSource = getFirstEventSource();

    act(() => {
      eventSource.emitTransportError();
    });

    await waitFor(() => {
      expect(result.current.isRunning).toBe(false);
      expect(result.current.messages[1]).toMatchObject({
        queryId: "query-transport",
        role: "assistant",
        status: "error",
      });
    });

    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });

  it("cancels the active SSE stream", async () => {
    postQueryMock.mockResolvedValue({ id: "query-3" });

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(
        makeAppendMessage("Cancel this Query")
      );
    });

    const eventSource = getFirstEventSource();

    await act(async () => {
      await result.current.adapter.onCancel?.();
    });

    expect(result.current.isRunning).toBe(false);
    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });

  it("maps Query history into assistant-ui thread-list items and resets on new thread", async () => {
    useQueryHistoryMock.mockReturnValue({
      data: [
        {
          completed_at: null,
          created_at: "2026-07-04T10:00:00Z",
          error_message: null,
          id: "query-4",
          query_text: "Explain the Simple Route",
          selected_route: "simple",
          status: "completed",
          updated_at: "2026-07-04T10:00:01Z",
        },
      ],
      isLoading: false,
    });
    fetchAnswerMock.mockResolvedValue({
      evidence: [],
      full_text: "The Simple Route uses one retrieval pass.",
      id: "answer-4",
      query_id: "query-4",
      segments: [],
    });
    postQueryMock.mockResolvedValue({ id: "query-5" });

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    expect(result.current.adapter.adapters?.threadList?.threads).toEqual([
      {
        id: "query-4",
        remoteId: "query-4",
        status: "regular",
        title: "Explain the Simple Route",
      },
    ]);

    await act(async () => {
      await result.current.adapter.adapters?.threadList?.onSwitchToThread?.(
        "query-4"
      );
    });

    expect(fetchAnswerMock).toHaveBeenCalledWith("query-4");
    expect(result.current.messages).toMatchObject([
      {
        contentParts: [{ type: "text", text: "Explain the Simple Route" }],
        queryId: "query-4",
        role: "user",
      },
      {
        contentParts: [
          { type: "text", text: "The Simple Route uses one retrieval pass." },
        ],
        hopProgress: [],
        queryId: "query-4",
        role: "assistant",
        route: "simple",
        status: "complete",
        subQueries: [],
      },
    ]);

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("Temporary Query"));
    });

    await act(async () => {
      await result.current.adapter.adapters?.threadList?.onSwitchToNewThread?.();
    });

    expect(result.current.messages).toEqual([]);

    const onDelete = result.current.adapter.adapters?.threadList?.onDelete;

    expect(onDelete).toBeTypeOf("function");
    await expect(onDelete?.("query-4")).resolves.toBeUndefined();
  });
});
