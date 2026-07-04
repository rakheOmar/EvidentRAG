import type { AppendMessage, ExternalStoreAdapter } from "@assistant-ui/react";
import { useExternalStoreRuntime } from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useRef, useState } from "react";

import { fetchAnswer, postQuery, queryKeys, useQueryHistory } from "@/lib/api";
import { convertEvidentMessage } from "@/lib/message-utils";
import type {
  DoneEvent,
  ErrorEvent,
  EvidentChatMessage,
  GeneratingEvent,
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

  const onCancel = useCallback(() => {
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

  const onSwitchToThread = useCallback(
    async (threadId: string) => {
      const query = historyQuery.data?.find((entry) => entry.id === threadId);

      if (query === undefined) {
        return;
      }

      const answerResponse = await fetchAnswer(threadId);
      const answer = isAnswerDetail(answerResponse) ? answerResponse : null;

      setCurrentThreadId(threadId);
      setIsRunning(false);
      setMessages([
        {
          content: query.query_text,
          createdAt: new Date(query.created_at),
          id: `${threadId}-user`,
          queryId: threadId,
          role: "user",
          status: "complete",
        },
        {
          answer,
          content: answer?.full_text ?? "",
          createdAt: new Date(),
          id: `${threadId}-assistant`,
          phase: "done",
          queryId: threadId,
          role: "assistant",
          route: query.selected_route,
          status: "complete",
        },
      ]);
    },
    [historyQuery.data]
  );

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
          content: queryText,
          createdAt: new Date(),
          id: userMessageId,
          role: "user",
          status: "complete",
        },
        {
          content: "",
          createdAt: new Date(),
          id: assistantMessageId,
          phase: "routing",
          role: "assistant",
          status: "running",
          streamedSentences: [],
        },
      ]);

      setIsRunning(true);

      const query = await postQuery(queryText);
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

      updateAssistantMessage((entry) => ({ ...entry, queryId: query.id }));

      eventSource.addEventListener(
        "route_selected",
        (event: MessageEvent<string>) => {
          const payload = JSON.parse(event.data) as RouteSelectedEvent;

          updateAssistantMessage((entry) => ({
            ...entry,
            phase: "routing",
            route: payload.route,
          }));
        }
      );

      eventSource.addEventListener("retrieving", () => {
        updateAssistantMessage((entry) => ({ ...entry, phase: "retrieving" }));
      });

      eventSource.addEventListener(
        "generating",
        (event: MessageEvent<string>) => {
          const payload = JSON.parse(event.data) as GeneratingEvent;

          updateAssistantMessage((entry) => {
            const streamedSentences = [
              ...(entry.streamedSentences ?? []),
              payload.sentence,
            ];

            return {
              ...entry,
              content: streamedSentences.join(" "),
              phase: "generating",
              streamedSentences,
            };
          });
        }
      );

      eventSource.addEventListener(
        "done",
        async (event: MessageEvent<string>) => {
          const payload = JSON.parse(event.data) as DoneEvent;
          const answerResponse = await fetchAnswer(query.id);
          const answer = isAnswerDetail(answerResponse) ? answerResponse : null;

          updateAssistantMessage((entry) => ({
            ...entry,
            answer,
            content: answer?.full_text ?? payload.full_text ?? entry.content,
            phase: "done",
            status: "complete",
          }));

          eventSource.close();
          eventSourceRef.current = null;
          setIsRunning(false);
          await queryClient.invalidateQueries({ queryKey: queryKeys.queries });
        }
      );

      eventSource.addEventListener("error", (event: Event) => {
        let errorMessage = "Stream disconnected.";

        if (
          event instanceof MessageEvent &&
          typeof event.data === "string" &&
          event.data.length > 0
        ) {
          try {
            const payload = JSON.parse(event.data) as ErrorEvent;
            errorMessage = payload.message;
          } catch {
            errorMessage = "Stream disconnected.";
          }
        }

        updateAssistantMessage((entry) => ({
          ...entry,
          errorMessage,
          phase: "error",
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
