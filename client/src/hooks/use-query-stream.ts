import { useEffect, useRef, useState } from "react";

import { postQuery } from "@/lib/api";
import type {
  DoneEvent,
  ErrorEvent,
  GeneratingEvent,
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
}

const INITIAL_STATE: StreamState = {
  donePayload: null,
  errorMessage: null,
  phase: "idle",
  queryId: null,
  route: null,
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
      streamedSentences: [],
    });

    eventSource.addEventListener(
      "route_selected",
      (event: MessageEvent<string>) => {
        const payload = JSON.parse(event.data) as RouteSelectedEvent;
        setState((current) => ({
          ...current,
          phase: "routing",
          route: payload.route,
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
      const payload = JSON.parse(event.data) as ErrorEvent;
      setState((current) => ({
        ...current,
        errorMessage: payload.message,
        phase: "error",
      }));
      eventSource.close();
      eventSourceRef.current = null;
    });
  }

  function reset() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setState(INITIAL_STATE);
  }

  return { reset, state, submit };
}
