import { useQuery } from "@tanstack/react-query";

import type { QueryAnswerResponse, QuerySummary } from "@/lib/types";

const queryKeys = {
  answer: (queryId: string) => ["answer", queryId] as const,
  queries: ["queries"] as const,
};

export async function postQuery(queryText: string): Promise<QuerySummary> {
  const response = await fetch("/api/v1/queries", {
    body: JSON.stringify({ query_text: queryText }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(
      `POST /api/v1/queries failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as QuerySummary;
}

export async function fetchQueryHistory(): Promise<QuerySummary[]> {
  const response = await fetch("/api/v1/queries", { method: "GET" });

  if (!response.ok) {
    throw new Error(
      `GET /api/v1/queries failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as QuerySummary[];
}

export async function fetchAnswer(
  queryId: string
): Promise<QueryAnswerResponse> {
  const response = await fetch(`/api/v1/queries/${queryId}/answer`, {
    method: "GET",
  });

  if (!response.ok) {
    throw new Error(
      `GET /api/v1/queries/${queryId}/answer failed: ${response.status} ${response.statusText}`
    );
  }

  return (await response.json()) as QueryAnswerResponse;
}

export function useQueryHistory() {
  return useQuery({
    queryFn: fetchQueryHistory,
    queryKey: queryKeys.queries,
    refetchOnWindowFocus: true,
  });
}

export function useAnswer(queryId: string | null) {
  return useQuery({
    enabled: queryId !== null,
    queryFn: () => {
      if (queryId === null) {
        throw new Error("queryId is required to fetch an answer.");
      }

      return fetchAnswer(queryId);
    },
    queryKey: queryId === null ? ["answer", "idle"] : queryKeys.answer(queryId),
  });
}

export { queryKeys };
