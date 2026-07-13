import { useQuery } from "@tanstack/react-query";
import { requestEmpty, requestJson } from "@/lib/errors";

import type {
  DocumentListResponse,
  DocumentRecord,
  SentenceTraceFeedbackResponse,
  ThreadDetail,
  ThreadSummary,
  ThreadTurnResponse,
} from "@/lib/types";

export interface ModelContextDetails {
  context_window: number;
  generation_model: string;
}

const queryKeys = {
  documents: ["documents"] as const,
  thread: (threadId: string) => ["thread", threadId] as const,
  threads: ["threads"] as const,
};

export function uploadDocument(
  file: File,
  sourceKey?: string,
): Promise<DocumentRecord> {
  const formData = new FormData();
  formData.set("file", file);
  if (sourceKey) {
    formData.set("source_key", sourceKey);
  }
  return requestJson<DocumentRecord>("/api/v1/documents", {
    body: formData,
    method: "POST",
  });
}

export function fetchDocuments(): Promise<DocumentListResponse> {
  return requestJson<DocumentListResponse>("/api/v1/documents", {
    method: "GET",
  });
}

export async function deleteDocument(documentId: string): Promise<void> {
  await requestEmpty(`/api/v1/documents/${documentId}`, { method: "DELETE" });
}

export async function createThread(
  content: string,
): Promise<ThreadTurnResponse> {
  return requestJson<ThreadTurnResponse>("/api/v1/threads", {
    body: JSON.stringify({ content }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export async function appendThreadMessage(
  threadId: string,
  content: string,
): Promise<ThreadTurnResponse> {
  return requestJson<ThreadTurnResponse>(`/api/v1/threads/${threadId}/messages`, {
    body: JSON.stringify({ content }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });
}

export async function fetchThreads(): Promise<ThreadSummary[]> {
  return requestJson<ThreadSummary[]>("/api/v1/threads", { method: "GET" });
}

export async function fetchThread(threadId: string): Promise<ThreadDetail> {
  return requestJson<ThreadDetail>(`/api/v1/threads/${threadId}`, {
    method: "GET",
  });
}

export async function fetchModelContext(): Promise<ModelContextDetails> {
  return requestJson<ModelContextDetails>("/api/v1/model-context", {
    method: "GET",
  });
}

export async function putSentenceTraceFeedback(
  traceId: string,
  rating: "up" | "down",
): Promise<SentenceTraceFeedbackResponse> {
  return requestJson<SentenceTraceFeedbackResponse>(`/api/v1/sentence-traces/${traceId}/rating`, {
    body: JSON.stringify({ rating }),
    headers: { "Content-Type": "application/json" },
    method: "PUT",
  });
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
