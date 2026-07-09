import type {
  AppendMessage,
  ExternalStoreAdapter,
  ThreadAssistantMessagePart,
} from "@assistant-ui/react";
import { useExternalStoreRuntime } from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";

import { fetchAnswer, postQuery, queryKeys, useQueryHistory } from "@/lib/api";
import { setMessageEvidence } from "@/lib/evidence-store";
import { convertEvidentMessage } from "@/lib/message-utils";
import { setMessageSegments } from "@/lib/segments-store";
import type {
  ContentPartsEvent,
  DoneEventWithContentParts,
  EvidentChatMessage,
  HopProgressEvent,
  ReasoningTraceEntry,
  RouteSelectedEvent,
} from "@/lib/types";
import { isAnswerDetail } from "@/lib/types";

function getMessageText(message: AppendMessage): string {
  return message.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join(" ");
}

export function useEvidentRuntime() {
  const [currentThreadId, setCurrentThreadId] = useState<string | undefined>();
  const [isRunning, setIsRunning] = useState(false);
  const [messages, setMessages] = useState<EvidentChatMessage[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const queryClient = useQueryClient();
  const historyQuery = useQueryHistory();
  const historyDataRef = useRef(historyQuery.data);
  historyDataRef.current = historyQuery.data;

  // biome-ignore lint/suspicious/useAwait: type contract requires Promise<void>
  const onCancel = useCallback(async () => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setIsRunning(false);
  }, []);

  const setRuntimeMessages = useCallback(
    (nextMessages: readonly EvidentChatMessage[]) => {
      setMessages([...nextMessages]);
    },
    []
  );

  const onSwitchToNewThread = useCallback(() => {
    setCurrentThreadId(undefined);
    setMessages([]);
    setIsRunning(false);
  }, []);

  const onSwitchToThread = useCallback(async (threadId: string) => {
    const query = historyDataRef.current?.find(
      (entry) => entry.id === threadId
    );

    const answerResponse = await fetchAnswer(threadId);
    const answer = isAnswerDetail(answerResponse) ? answerResponse : null;
    const contentParts: ThreadAssistantMessagePart[] = answer
      ? [{ type: "text", text: answer.full_text }]
      : [];

    if (answer?.segments) {
      setMessageSegments(`${threadId}-assistant`, answer.segments);
    }
    if (answer?.evidence) {
      setMessageEvidence(`${threadId}-assistant`, answer.evidence);
    }

    const reasoningTrace = answer?.reasoning_trace ?? [];
    const hopProgress = reasoningTrace
      .filter(
        (t): t is Extract<ReasoningTraceEntry, { type: "hop" }> =>
          t.type === "hop"
      )
      .map((t) => ({
        hop: t.hop,
        intermediate_answer: t.intermediate_answer,
        sub_query: t.sub_query,
      }));

    setCurrentThreadId(threadId);
    setIsRunning(false);

    if (query) {
      setMessages([
        {
          contentParts: [{ type: "text", text: query.query_text }],
          createdAt: new Date(query.created_at),
          id: `${threadId}-user`,
          queryId: threadId,
          role: "user",
          status: "complete",
        },
        {
          contentParts,
          createdAt: new Date(),
          hopProgress,
          id: `${threadId}-assistant`,
          queryId: threadId,
          reasoningTrace,
          role: "assistant",
          route: query.selected_route ?? undefined,
          status: "complete",
          subQueries: query.sub_queries ?? [],
        },
      ]);
    }
  }, []);

  const onDeleteThread = useCallback(async (_threadId: string) => {
    // EvidentRAG does not expose thread deletion yet.
  }, []);

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const queryText = getMessageText(message);
      const assistantMessageId = crypto.randomUUID();
      const userMessageId = crypto.randomUUID();

      setMessages((current) => [
        ...current,
        {
          contentParts: [{ type: "text", text: queryText }],
          createdAt: new Date(),
          id: userMessageId,
          role: "user",
          status: "complete",
        },
        {
          contentParts: [],
          createdAt: new Date(),
          generating: false,
          hopProgress: [],
          id: assistantMessageId,
          reasoningTrace: [],
          role: "assistant",
          status: "running",
          subQueries: [],
        },
      ]);

      setIsRunning(true);

      const query = await postQuery(queryText);
      setCurrentThreadId(query.id);
      const eventSource = new EventSource(`/api/v1/queries/${query.id}/events`);
      eventSourceRef.current = eventSource;

      const updateAssistantMessage = (
        updater: (message: EvidentChatMessage) => EvidentChatMessage
      ) => {
        setMessages((current) =>
          current.map((entry) =>
            entry.id === assistantMessageId ? updater(entry) : entry
          )
        );
      };

      updateAssistantMessage((entry) => ({
        ...entry,
        queryId: query.id,
        contentParts: [{ type: "reasoning", text: "Starting..." }],
      }));

      eventSource.addEventListener(
        "route_selected",
        (event: MessageEvent<string>) => {
          const payload = JSON.parse(event.data) as RouteSelectedEvent;

          updateAssistantMessage((entry) => ({
            ...entry,
            route: payload.route,
            subQueries: payload.sub_queries,
          }));
        }
      );

      eventSource.addEventListener(
        "hop_progress",
        (event: MessageEvent<string>) => {
          const payload = JSON.parse(event.data) as HopProgressEvent;

          const hopEntry: ReasoningTraceEntry = {
            type: "hop",
            hop: payload.hop,
            intermediate_answer: payload.intermediate_answer,
            sub_query: payload.sub_query,
          };
          updateAssistantMessage((entry) => {
            const trace = entry.reasoningTrace ?? [];
            const last = trace.at(-1);
            const exists = last?.type === "hop" && last.hop === payload.hop;
            return {
              ...entry,
              hopProgress: [...(entry.hopProgress ?? []), payload],
              reasoningTrace: exists ? trace : [...trace, hopEntry],
            };
          });
        }
      );

      eventSource.addEventListener(
        "content_parts",
        (event: MessageEvent<string>) => {
          const payload = JSON.parse(event.data) as ContentPartsEvent;
          const stepText = payload.parts
            .filter((p) => p.type === "reasoning")
            .map((p) => (p as { text?: string }).text ?? "")
            .join(" ")
            .trim();

          updateAssistantMessage((entry) => {
            const trace = entry.reasoningTrace ?? [];
            const last = trace.at(-1);
            const exists = last?.type === "step" && last.text === stepText;
            const hasAnswerText = payload.parts.some((p) => p.type === "text");
            return {
              ...entry,
              contentParts: payload.parts,
              generating: entry.generating || hasAnswerText,
              status: "running",
              reasoningTrace:
                stepText && !exists
                  ? [...trace, { type: "step", text: stepText }]
                  : trace,
            };
          });
        }
      );

      eventSource.addEventListener("done", (event: MessageEvent<string>) => {
        const payload = JSON.parse(event.data) as DoneEventWithContentParts;

        if (payload.error) {
          updateAssistantMessage((entry) => ({
            ...entry,
            status: "error",
          }));
        } else {
          if (payload.segments) {
            setMessageSegments(assistantMessageId, payload.segments);
          }
          const displayParts = payload.content_parts.filter(
            (p) => p.type !== "source"
          );
          updateAssistantMessage((entry) => ({
            ...entry,
            contentParts: displayParts,
            reasoningTrace: payload.reasoning_trace ?? entry.reasoningTrace,
            hopProgress:
              entry.hopProgress && entry.hopProgress.length > 0
                ? entry.hopProgress
                : (payload.reasoning_trace ?? [])
                    .filter(
                      (t): t is Extract<ReasoningTraceEntry, { type: "hop" }> =>
                        t.type === "hop"
                    )
                    .map((t) => ({
                      hop: t.hop,
                      intermediate_answer: t.intermediate_answer,
                      sub_query: t.sub_query,
                    })),
            status: "complete",
          }));

          fetchAnswer(payload.query_id)
            .then((answerResponse) => {
              const answer = isAnswerDetail(answerResponse)
                ? answerResponse
                : null;
              if (answer?.evidence) {
                setMessageEvidence(
                  `${payload.query_id}-assistant`,
                  answer.evidence
                );
              }
            })
            .catch(() => {
              /* evidence fetch is best-effort */
            });
        }

        eventSource.close();
        eventSourceRef.current = null;
        setIsRunning(false);
        queryClient.invalidateQueries({ queryKey: queryKeys.queries });
      });

      eventSource.addEventListener("error", () => {
        updateAssistantMessage((entry) => ({
          ...entry,
          status: "error",
        }));

        eventSource.close();
        eventSourceRef.current = null;
        setIsRunning(false);
      });
    },
    [queryClient]
  );

  const adapter = useMemo<ExternalStoreAdapter<EvidentChatMessage>>(
    () => ({
      adapters: {
        threadList: {
          isLoading: historyQuery.isLoading,
          onDelete: onDeleteThread,
          onSwitchToNewThread,
          onSwitchToThread,
          threadId: currentThreadId,
          threads:
            historyQuery.data?.map((query) => ({
              id: query.id,
              remoteId: query.id,
              status: "regular" as const,
              title: query.query_text,
            })) ?? [],
        },
      },
      convertMessage: convertEvidentMessage,
      isRunning,
      messages,
      onCancel,
      onNew,
      setMessages: setRuntimeMessages,
    }),
    [
      currentThreadId,
      historyQuery.data,
      historyQuery.isLoading,
      isRunning,
      messages,
      onCancel,
      onDeleteThread,
      onNew,
      onSwitchToNewThread,
      onSwitchToThread,
      setRuntimeMessages,
    ]
  );

  const runtime = useExternalStoreRuntime(adapter);

  return { adapter, isRunning, messages, runtime };
}
