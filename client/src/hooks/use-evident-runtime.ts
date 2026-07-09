import type {
  AppendMessage,
  ExternalStoreAdapter,
  ThreadAssistantMessagePart,
} from "@assistant-ui/react";
import { useExternalStoreRuntime } from "@assistant-ui/react";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";

import {
  appendThreadMessage,
  createThread,
  fetchThread,
  queryKeys,
  useThreadHistory,
} from "@/lib/api";
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
  ThreadMessage,
  ThreadTurnResponse,
} from "@/lib/types";

function getMessageText(message: AppendMessage): string {
  return message.content
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join(" ");
}

function toAssistantStatus(
  message: ThreadMessage
): EvidentChatMessage["status"] {
  if (message.role !== "assistant") {
    return "complete";
  }
  if (message.status === "failed") {
    return "error";
  }
  if (message.status === "completed") {
    return "complete";
  }
  return "running";
}

function toRuntimeMessage(message: ThreadMessage): EvidentChatMessage {
  const answer = message.answer ?? null;
  const contentParts: ThreadAssistantMessagePart[] =
    message.role === "assistant"
      ? // biome-ignore lint/suspicious/noUnnecessaryConditions: AnswerDetail.content_parts is optional, so the ?? fallback is required (false positive from Biome's module-graph panic)
        (answer?.content_parts?.filter((part) => part.type !== "source") ??
          (answer ? [{ text: answer.full_text, type: "text" }] : []))
      : [{ text: message.content_text, type: "text" }];

  if (answer?.segments) {
    setMessageSegments(message.id, answer.segments);
  }
  if (answer?.evidence) {
    setMessageEvidence(message.id, answer.evidence);
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

  return {
    contentParts,
    createdAt: new Date(message.created_at),
    hopProgress,
    id: message.id,
    messageId: message.id,
    reasoningTrace,
    role: message.role,
    route: message.selected_route ?? undefined,
    status: toAssistantStatus(message),
    subQueries: message.sub_queries,
    threadId: message.thread_id,
  };
}

function replacePendingMessages(
  current: EvidentChatMessage[],
  response: ThreadTurnResponse,
  queryText: string
) {
  const next = [...current];
  if (next.length >= 2) {
    next.splice(next.length - 2, 2);
  }
  next.push(
    {
      contentParts: [{ text: queryText, type: "text" }],
      createdAt: new Date(response.user_message.created_at),
      id: response.user_message.id,
      messageId: response.user_message.id,
      role: "user",
      status: "complete",
      threadId: response.thread.id,
    },
    {
      contentParts: [{ text: "Starting...", type: "reasoning" }],
      createdAt: new Date(response.assistant_message.created_at),
      id: response.assistant_message.id,
      messageId: response.assistant_message.id,
      role: "assistant",
      status: "running",
      subQueries: response.assistant_message.sub_queries,
      threadId: response.thread.id,
    }
  );
  return next;
}

export function useEvidentRuntime() {
  const navigate = useNavigate();
  const { threadId: routeThreadId } = useParams<{ threadId?: string }>();
  const [currentThreadId, setCurrentThreadId] = useState<string | undefined>();
  const [isRunning, setIsRunning] = useState(false);
  const [messages, setMessages] = useState<EvidentChatMessage[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const loadedThreadIdRef = useRef<string | undefined>(undefined);
  const queryClient = useQueryClient();
  const historyQuery = useThreadHistory();
  const historyDataRef = useRef(historyQuery.data);
  historyDataRef.current = historyQuery.data;

  const onCancel = useCallback(async () => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setIsRunning(false);
    await Promise.resolve();
  }, []);

  const setRuntimeMessages = useCallback(
    (nextMessages: readonly EvidentChatMessage[]) => {
      setMessages([...nextMessages]);
    },
    []
  );

  const onSwitchToNewThread = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setCurrentThreadId(undefined);
    setMessages([]);
    setIsRunning(false);
    loadedThreadIdRef.current = undefined;
    navigate("/chat");
  }, [navigate]);

  const onSwitchToThread = useCallback(
    (threadId: string) => {
      navigate(`/chat/${threadId}`);
    },
    [navigate]
  );

  const onDeleteThread = useCallback(async (_threadId: string) => {
    // EvidentRAG does not expose thread deletion yet.
  }, []);

  const loadThread = useCallback(async (threadId: string) => {
    const thread = await fetchThread(threadId);
    loadedThreadIdRef.current = thread.id;
    setCurrentThreadId(thread.id);
    setIsRunning(false);
    setMessages(thread.messages.map(toRuntimeMessage));
  }, []);

  useEffect(() => {
    if (routeThreadId === undefined) {
      loadedThreadIdRef.current = undefined;
      setCurrentThreadId(undefined);
      setMessages([]);
      setIsRunning(false);
      return;
    }
    if (loadedThreadIdRef.current === routeThreadId) {
      return;
    }
    loadThread(routeThreadId).catch(() => {
      loadedThreadIdRef.current = undefined;
    });
  }, [loadThread, routeThreadId]);

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const queryText = getMessageText(message);
      const optimisticUserId = crypto.randomUUID();
      const optimisticAssistantId = crypto.randomUUID();

      setMessages((current) => [
        ...current,
        {
          contentParts: [{ text: queryText, type: "text" }],
          createdAt: new Date(),
          id: optimisticUserId,
          role: "user",
          status: "complete",
        },
        {
          contentParts: [],
          createdAt: new Date(),
          generating: false,
          hopProgress: [],
          id: optimisticAssistantId,
          reasoningTrace: [],
          role: "assistant",
          status: "running",
          subQueries: [],
        },
      ]);

      setIsRunning(true);

      const response = currentThreadId
        ? await appendThreadMessage(currentThreadId, queryText)
        : await createThread(queryText);

      setCurrentThreadId(response.thread.id);
      loadedThreadIdRef.current = response.thread.id;
      setMessages((current) =>
        replacePendingMessages(current, response, queryText)
      );
      if (routeThreadId !== response.thread.id) {
        navigate(`/chat/${response.thread.id}`);
      }

      const assistantMessageId = response.assistant_message.id;
      const threadId = response.thread.id;
      const eventSource = new EventSource(
        `/api/v1/threads/${threadId}/messages/${assistantMessageId}/events`
      );
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
            hop: payload.hop,
            intermediate_answer: payload.intermediate_answer,
            sub_query: payload.sub_query,
            type: "hop",
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
              reasoningTrace:
                stepText && !exists
                  ? [...trace, { text: stepText, type: "step" }]
                  : trace,
              status: "running",
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
          if (payload.evidence) {
            setMessageEvidence(assistantMessageId, payload.evidence);
          }
          const displayParts = payload.content_parts.filter(
            (p) => p.type !== "source"
          );
          updateAssistantMessage((entry) => ({
            ...entry,
            contentParts: displayParts,
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
            reasoningTrace: payload.reasoning_trace ?? entry.reasoningTrace,
            status: "complete",
          }));
        }

        eventSource.close();
        eventSourceRef.current = null;
        setIsRunning(false);
        queryClient.invalidateQueries({ queryKey: queryKeys.threads });
        queryClient.invalidateQueries({ queryKey: queryKeys.thread(threadId) });
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
    [currentThreadId, navigate, queryClient, routeThreadId]
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
            historyQuery.data?.map((thread) => ({
              id: thread.id,
              remoteId: thread.id,
              status: "regular" as const,
              title: thread.title,
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
