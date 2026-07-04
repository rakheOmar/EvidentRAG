import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useQueryStream } from "../use-query-stream";

const postQueryMock = vi.fn();

vi.mock("@/lib/api", () => ({
  postQuery: (...args: unknown[]) => postQueryMock(...args),
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

  removeEventListener(
    type: string,
    listener: (event: MessageEvent<string>) => void
  ) {
    this.listeners.get(type)?.delete(listener);
  }

  emit(type: string, payload: unknown) {
    const event = { data: JSON.stringify(payload) } as MessageEvent<string>;
    for (const listener of this.listeners.get(type) ?? []) {
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

describe("useQueryStream", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    postQueryMock.mockReset();
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits a query, streams events through done, and closes the EventSource", async () => {
    postQueryMock.mockResolvedValue({ id: "q-001" });

    const { result } = renderHook(() => useQueryStream());

    await act(async () => {
      await result.current.submit("What is RAG?");
    });

    expect(postQueryMock).toHaveBeenCalledWith("What is RAG?");
    expect(FakeEventSource.instances).toHaveLength(1);

    const eventSource = getFirstEventSource();
    expect(eventSource.url).toBe("/api/v1/queries/q-001/events");

    act(() => {
      eventSource.emit("route_selected", { route: "simple" });
      eventSource.emit("retrieving", { status: "retrieving" });
      eventSource.emit("generating", { sentence: "Sentence one." });
      eventSource.emit("generating", { sentence: "Sentence two." });
      eventSource.emit("done", {
        evidence: [],
        full_text: "Sentence one. Sentence two.",
        id: "a-001",
        query_id: "q-001",
        sentences: [],
      });
    });

    await waitFor(() => {
      expect(result.current.state).toEqual({
        donePayload: {
          evidence: [],
          full_text: "Sentence one. Sentence two.",
          id: "a-001",
          query_id: "q-001",
          sentences: [],
        },
        errorMessage: null,
        phase: "done",
        queryId: "q-001",
        route: "simple",
        streamedSentences: ["Sentence one.", "Sentence two."],
      });
    });

    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });

  it("stores an error message, moves to the error phase, and closes the EventSource", async () => {
    postQueryMock.mockResolvedValue({ id: "q-002" });

    const { result } = renderHook(() => useQueryStream());

    await act(async () => {
      await result.current.submit("Break please");
    });

    const eventSource = getFirstEventSource();

    act(() => {
      eventSource.emit("error", { message: "Worker exploded" });
    });

    await waitFor(() => {
      expect(result.current.state).toEqual({
        donePayload: null,
        errorMessage: "Worker exploded",
        phase: "error",
        queryId: "q-002",
        route: null,
        streamedSentences: [],
      });
    });

    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });

  it("closes the active EventSource when the hook unmounts", async () => {
    postQueryMock.mockResolvedValue({ id: "q-003" });

    const { result, unmount } = renderHook(() => useQueryStream());

    await act(async () => {
      await result.current.submit("Unmount me");
    });

    const eventSource = getFirstEventSource();

    unmount();

    expect(eventSource.close).toHaveBeenCalledTimes(1);
  });
});
