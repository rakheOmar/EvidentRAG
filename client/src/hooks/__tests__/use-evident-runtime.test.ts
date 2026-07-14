import type { AppendMessage, ExternalStoreAdapter } from "@assistant-ui/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/errors";
import type {
  EvidentChatMessage,
  ThreadDetail,
  ThreadSummary,
  ThreadTurnResponse,
} from "@/lib/types";
import { useEvidentRuntime } from "../use-evident-runtime";

const appendThreadMessageMock = vi.fn();
const createThreadMock = vi.fn();
const fetchThreadMock = vi.fn();
const navigateMock = vi.fn();
let routeThreadId: string | undefined;
const useExternalStoreRuntimeMock = vi.fn(
  (adapter: ExternalStoreAdapter<EvidentChatMessage>) => adapter
);
const useThreadHistoryMock = vi.fn<
  () => { data: ThreadSummary[]; isLoading: boolean }
>(() => ({
  data: [],
  isLoading: false,
}));

vi.mock("@assistant-ui/react", () => ({
  useExternalStoreRuntime: (
    adapter: ExternalStoreAdapter<EvidentChatMessage>
  ) => useExternalStoreRuntimeMock(adapter),
}));

vi.mock("react-router", async () => {
  const actual =
    await vi.importActual<typeof import("react-router")>("react-router");

  return {
    ...actual,
    useNavigate: () => navigateMock,
    useParams: () => ({ threadId: routeThreadId }),
  };
});

vi.mock("@/lib/api", () => ({
  appendThreadMessage: (...args: unknown[]) => appendThreadMessageMock(...args),
  createThread: (...args: unknown[]) => createThreadMock(...args),
  fetchThread: (...args: unknown[]) => fetchThreadMock(...args),
  queryKeys: {
    thread: (threadId: string) => ["thread", threadId],
    threads: ["threads"],
  },
  useThreadHistory: () => useThreadHistoryMock(),
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
  const [eventSource] = FakeEventSource.instances;

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

function makeThreadSummary(
  overrides: Partial<ThreadSummary> = {}
): ThreadSummary {
  return {
    created_at: "2026-07-04T10:00:00Z",
    id: "thread-1",
    summary: "",
    title: "What is BERT",
    updated_at: "2026-07-04T10:00:00Z",
    ...overrides,
  };
}

function makeTurnResponse(
  overrides: Partial<ThreadTurnResponse> = {}
): ThreadTurnResponse {
  return {
    assistant_message: {
      completed_at: null,
      content_text: "",
      created_at: "2026-07-04T10:00:01Z",
      error_message: null,
      id: "assistant-1",
      position: 1,
      reply_to_message_id: "user-1",
      role: "assistant",
      selected_route: null,
      status: "pending",
      sub_queries: [],
      thread_id: "thread-1",
      updated_at: "2026-07-04T10:00:01Z",
    },
    thread: makeThreadSummary(),
    user_message: {
      completed_at: "2026-07-04T10:00:00Z",
      content_text: "What is BERT?",
      created_at: "2026-07-04T10:00:00Z",
      error_message: null,
      id: "user-1",
      position: 0,
      reply_to_message_id: null,
      role: "user",
      selected_route: null,
      status: "completed",
      sub_queries: [],
      thread_id: "thread-1",
      updated_at: "2026-07-04T10:00:00Z",
    },
    ...overrides,
  };
}

describe("useEvidentRuntime", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    appendThreadMessageMock.mockReset();
    createThreadMock.mockReset();
    fetchThreadMock.mockReset();
    navigateMock.mockReset();
    routeThreadId = undefined;
    useExternalStoreRuntimeMock.mockClear();
    useThreadHistoryMock.mockReset();
    useThreadHistoryMock.mockReturnValue({ data: [], isLoading: false });
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("creates a thread and streams assistant completion", async () => {
    createThreadMock.mockResolvedValue(makeTurnResponse());

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("What is BERT?"));
    });

    expect(createThreadMock).toHaveBeenCalledWith("What is BERT?");
    expect(navigateMock).toHaveBeenCalledWith("/chat/thread-1");

    const eventSource = getFirstEventSource();
    expect(eventSource.url).toBe(
      "/api/v1/threads/thread-1/messages/assistant-1/events"
    );

    act(() => {
      eventSource.emit("route_selected", {
        route: "simple",
        sub_queries: [],
      });
    });

    act(() => {
      eventSource.emit("content_parts", {
        parts: [{ text: "Routing Query...", type: "reasoning" }],
      });
    });

    act(() => {
      eventSource.emit("done", {
        content_parts: [
          {
            text: "BERT is a bidirectional transformer encoder.",
            type: "text",
          },
        ],
        error: false,
        evidence: [],
        full_text: "BERT is a bidirectional transformer encoder.",
        id: "answer-1",
        message_id: "assistant-1",
        reasoning_trace: [],
        segments: [],
        thread_id: "thread-1",
      });
    });

    await waitFor(() => {
      expect(result.current.isRunning).toBe(false);
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[0]).toMatchObject({
        contentParts: [{ text: "What is BERT?", type: "text" }],
        role: "user",
        threadId: "thread-1",
      });
      expect(result.current.messages[1]).toMatchObject({
        contentParts: [
          {
            text: "BERT is a bidirectional transformer encoder.",
            type: "text",
          },
        ],
        messageId: "assistant-1",
        role: "assistant",
        route: "simple",
        status: "complete",
        subQueries: [],
        threadId: "thread-1",
      });
    });
  });

  it("trims the submitted prompt before displaying or sending it", async () => {
    createThreadMock.mockResolvedValue(makeTurnResponse());

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(
        makeAppendMessage("  What is BERT?  \n")
      );
    });

    expect(createThreadMock).toHaveBeenCalledWith("What is BERT?");
    expect(result.current.messages[0]?.contentParts).toEqual([
      { text: "What is BERT?", type: "text" },
    ]);
  });

  it("does not create an optimistic message for an empty prompt", async () => {
    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("  \n  "));
    });

    expect(createThreadMock).not.toHaveBeenCalled();
    expect(appendThreadMessageMock).not.toHaveBeenCalled();
    expect(result.current.messages).toEqual([]);
    expect(result.current.isRunning).toBe(false);
  });

  it("shows inline API validation failures on the assistant message", async () => {
    createThreadMock.mockRejectedValue(
      new ApiError("Content is required", 422, { code: "validation_error" })
    );

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("Explain failures"));
    });

    await waitFor(() => {
      expect(result.current.isRunning).toBe(false);
      expect(result.current.messages).toHaveLength(2);
      expect(result.current.messages[1]).toMatchObject({
        contentParts: [{ text: "Content is required", type: "text" }],
        role: "assistant",
        status: "error",
      });
    });
    expect(FakeEventSource.instances).toHaveLength(0);
  });

  it("appends a follow-up to the active thread", async () => {
    createThreadMock.mockResolvedValue(makeTurnResponse());
    const followUpResponse = makeTurnResponse();
    appendThreadMessageMock.mockResolvedValue(
      makeTurnResponse({
        assistant_message: {
          ...followUpResponse.assistant_message,
          id: "assistant-2",
          position: 3,
          reply_to_message_id: "user-2",
        },
        user_message: {
          ...followUpResponse.user_message,
          content_text: "What is HNSW?",
          id: "user-2",
          position: 2,
        },
      })
    );

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("What is BERT?"));
    });

    getFirstEventSource().close.mockClear();
    FakeEventSource.instances = [];

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("What is HNSW?"));
    });

    expect(appendThreadMessageMock).toHaveBeenCalledWith(
      "thread-1",
      "What is HNSW?"
    );
    expect(getFirstEventSource().url).toBe(
      "/api/v1/threads/thread-1/messages/assistant-2/events"
    );
  });

  it("loads a persisted thread from the route parameter", async () => {
    routeThreadId = "thread-1";
    useThreadHistoryMock.mockReturnValue({
      data: [makeThreadSummary()],
      isLoading: false,
    });
    const persistedResponse = makeTurnResponse();
    fetchThreadMock.mockResolvedValue({
      ...makeThreadSummary(),
      messages: [
        persistedResponse.user_message,
        {
          ...persistedResponse.assistant_message,
          answer: {
            content_parts: [
              {
                text: "BERT is a bidirectional transformer encoder.",
                type: "text",
              },
            ],
            evidence: [],
            full_text: "BERT is a bidirectional transformer encoder.",
            id: "answer-1",
            message_id: "assistant-1",
            reasoning_trace: [],
            segments: [],
          },
          selected_route: "simple",
          status: "completed",
        },
      ],
      summary: "",
      title: "What is BERT",
      updated_at: "2026-07-04T10:00:00Z",
    } satisfies ThreadDetail);

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(fetchThreadMock).toHaveBeenCalledWith("thread-1");
    });

    expect(result.current.adapter.adapters?.threadList?.threads).toEqual([
      {
        id: "thread-1",
        lastMessageAt: new Date("2026-07-04T10:00:00Z"),
        remoteId: "thread-1",
        status: "regular",
        title: "What is BERT",
      },
    ]);
    await waitFor(() => {
      expect(result.current.messages).toMatchObject([
        {
          contentParts: [{ text: "What is BERT?", type: "text" }],
          role: "user",
        },
        {
          contentParts: [
            {
              text: "BERT is a bidirectional transformer encoder.",
              type: "text",
            },
          ],
          role: "assistant",
          route: "simple",
          status: "complete",
        },
      ]);
    });
  });

  it("navigates to a selected thread from the thread list", async () => {
    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.adapters?.threadList?.onSwitchToThread?.(
        "thread-42"
      );
    });

    expect(navigateMock).toHaveBeenCalledWith("/chat/thread-42");
  });

  it("returns to the base chat route for a new thread", () => {
    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.adapter.adapters?.threadList?.onSwitchToNewThread?.();
    });

    expect(navigateMock).toHaveBeenCalledWith("/chat");
  });

  it("keeps a running answer recoverable while EventSource reconnects", async () => {
    createThreadMock.mockResolvedValue(makeTurnResponse());

    const { result } = renderHook(() => useEvidentRuntime(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.adapter.onNew(makeAppendMessage("Explain failures"));
    });

    const eventSource = getFirstEventSource();

    act(() => {
      eventSource.emitTransportError();
    });

    await waitFor(() => {
      expect(result.current.isRunning).toBe(true);
      expect(result.current.messages[1]).toMatchObject({
        messageId: "assistant-1",
        role: "assistant",
        status: "running",
      });
    });
    expect(eventSource.close).not.toHaveBeenCalled();
  });
});
