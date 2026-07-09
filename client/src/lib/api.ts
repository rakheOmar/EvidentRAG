import { useQuery } from "@tanstack/react-query";

import type {
  ThreadDetail,
  ThreadSummary,
  ThreadTurnResponse,
} from "@/lib/types";

const queryKeys = {
  thread: (threadId: string) => ["thread", threadId] as const,
  threads: ["threads"] as const,
};

export async function createThread(
  content: string
): Promise<ThreadTurnResponse> {
  const response = await fetch("/api/v1/threads", {
    body: JSON.stringify({ content }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(
      `POST /api/v1/threads failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as ThreadTurnResponse;
}

export async function appendThreadMessage(
  threadId: string,
  content: string
): Promise<ThreadTurnResponse> {
  const response = await fetch(`/api/v1/threads/${threadId}/messages`, {
    body: JSON.stringify({ content }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(
      `POST /api/v1/threads/${threadId}/messages failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as ThreadTurnResponse;
}

export async function fetchThreads(): Promise<ThreadSummary[]> {
  const response = await fetch("/api/v1/threads", { method: "GET" });

  if (!response.ok) {
    throw new Error(
      `GET /api/v1/threads failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as ThreadSummary[];
}

export async function fetchThread(threadId: string): Promise<ThreadDetail> {
  const response = await fetch(`/api/v1/threads/${threadId}`, {
    method: "GET",
  });

  if (!response.ok) {
    throw new Error(
      `GET /api/v1/threads/${threadId} failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as ThreadDetail;
}

export function useThreadHistory() {
  return useQuery({
    queryFn: fetchThreads,
    queryKey: queryKeys.threads,
    refetchOnWindowFocus: true,
  });
}

export function useThread(threadId: string | null) {
  return useQuery({
    enabled: threadId !== null,
    queryFn: () => {
      if (threadId === null) {
        throw new Error("threadId is required to fetch a thread.");
      }

      return fetchThread(threadId);
    },
    queryKey:
      threadId === null ? ["thread", "idle"] : queryKeys.thread(threadId),
  });
}

export { queryKeys };
