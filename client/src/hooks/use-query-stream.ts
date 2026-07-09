import { useEffect, useRef, useState } from "react";

import { fetchAnswer, postQuery } from "@/lib/api";
import type {
  DoneEvent,
  ErrorEvent,
  GeneratingEvent,
  PendingAnswerResponse,
  QueryAnswerResponse,
  RouteSelectedEvent,
} from "@/lib/types";

export type StreamPhase =
  | "idle"
  | "routing"
  | "retrieving"
  | "generating"
  | "done"
  | "error";

export interface StreamState {
  donePayload: DoneEvent | null;
  errorMessage: string | null;
  phase: StreamPhase;
  queryId: string | null;
  route: string | null;
  streamedSentences: string[];
  subQueries: string[];
}

const INITIAL_STATE: StreamState = {
  donePayload: null,
  errorMessage: null,
  phase: "idle",
  queryId: null,
  route: null,
  subQueries: [],
  streamedSentences: [],
};

export function useQueryStream() {
  const [state, setState] = useState<StreamState>(INITIAL_STATE);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(
    () => () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    },
    []
  );

  async function submit(queryText: string) {
    eventSourceRef.current?.close();

    const query = await postQuery(queryText);
    const eventSource = new EventSource(`/api/v1/queries/${query.id}/events`);
    eventSourceRef.current = eventSource;

    setState({
      donePayload: null,
      errorMessage: null,
      phase: "routing",
      queryId: query.id,
      route: null,
      subQueries: [],
      streamedSentences: [],
    });

    let resolved = false;
    const resolveFromAnswer = async () => {
      if (resolved) {
        return;
      }
      resolved = true;
      const answer = await pollAnswerUntilReady(query.id);
      if (answer === null) {
        return;
      }
      if ("status" in answer && answer.status === "pending") {
        return;
      }
      setState((current) => ({
        ...current,
        donePayload: answer as DoneEvent,
        phase: "done",
      }));
    };

    eventSource.addEventListener(
      "route_selected",
      (event: MessageEvent<string>) => {
        const payload = JSON.parse(event.data) as RouteSelectedEvent;
        setState((current) => ({
          ...current,
          phase: "routing",
          route: payload.route,
          subQueries: payload.sub_queries,
        }));
      }
    );

    eventSource.addEventListener("retrieving", () => {
      setState((current) => ({ ...current, phase: "retrieving" }));
    });

    eventSource.addEventListener(
      "generating",
      (event: MessageEvent<string>) => {
        const payload = JSON.parse(event.data) as GeneratingEvent;
        setState((current) => ({
          ...current,
          phase: "generating",
          streamedSentences: [...current.streamedSentences, payload.sentence],
        }));
      }
    );

    eventSource.addEventListener("done", (event: MessageEvent<string>) => {
      resolved = true;
      const payload = JSON.parse(event.data) as DoneEvent;
      setState((current) => ({
        ...current,
        donePayload: payload,
        phase: "done",
      }));
      eventSource.close();
      eventSourceRef.current = null;
    });

    eventSource.addEventListener("error", (event: MessageEvent<string>) => {
      if (resolved) {
        return;
      }
      if (event.data) {
        const payload = JSON.parse(event.data) as ErrorEvent;
        setState((current) => ({
          ...current,
          errorMessage: payload.message,
          phase: "error",
        }));
        eventSource.close();
        eventSourceRef.current = null;
        return;
      }
      eventSource.close();
      eventSourceRef.current = null;
      resolveFromAnswer();
    });
  }

  function reset() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setState(INITIAL_STATE);
  }

  return { reset, state, submit };
}

const ANSWER_POLL_INTERVAL_MS = 1500;
const ANSWER_POLL_TIMEOUT_MS = 180_000;

async function pollAnswerUntilReady(
  queryId: string
): Promise<QueryAnswerResponse | PendingAnswerResponse | null> {
  const deadline = Date.now() + ANSWER_POLL_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const answer = await fetchAnswer(queryId);
      const pending = "status" in answer && answer.status === "pending";
      if (!pending) {
        return answer;
      }
    } catch {
      // ignore transient fetch errors and keep polling
    }
    await new Promise((resolve) =>
      setTimeout(resolve, ANSWER_POLL_INTERVAL_MS)
    );
  }
  return null;
}
