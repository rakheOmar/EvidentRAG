import type { ThreadMessageLike } from "@assistant-ui/react";

import type { EvidentChatMessage } from "@/lib/types";

function toMessageStatus(
  status: EvidentChatMessage["status"]
): ThreadMessageLike["status"] {
  switch (status) {
    case "running":
      return { type: "running" };
    case "complete":
      return { type: "complete", reason: "stop" };
    case "error":
      return { type: "incomplete", reason: "error" };
    default:
      return { type: "complete", reason: "stop" };
  }
}

export function convertEvidentMessage(
  message: EvidentChatMessage
): ThreadMessageLike {
  if (message.role === "assistant" && message.phase === "routing") {
    const routeName = message.route === "simple" ? "Simple Route" : "Route";

    return {
      content: [
        { text: `Routing Query via the ${routeName}...`, type: "reasoning" },
      ],
      createdAt: message.createdAt,
      id: message.id,
      role: message.role,
      status: toMessageStatus(message.status),
    };
  }

  if (message.role === "assistant" && message.phase === "done") {
    const textPart = { text: message.content, type: "text" as const };
    const evidence = Array.isArray(message.answer?.evidence)
      ? message.answer.evidence
      : [];
    const sourceParts = evidence.map((ev) => ({
      filename: ev.document_slug ?? undefined,
      id: ev.id,
      mediaType: "text/plain",
      providerMetadata: {
        evidentrag: {
          contextHeader: ev.context_header,
          page: ev.page,
        },
      },
      sourceType: "document" as const,
      title: ev.document_title ?? ev.id,
      type: "source" as const,
    }));

    return {
      content: [textPart, ...sourceParts],
      createdAt: message.createdAt,
      id: message.id,
      role: message.role,
      status: toMessageStatus(message.status),
    };
  }

  if (message.role === "assistant") {
    return {
      content: [{ text: message.content, type: "text" }],
      createdAt: message.createdAt,
      id: message.id,
      role: message.role,
      status: toMessageStatus(message.status),
    };
  }

  return {
    content: [{ text: message.content, type: "text" }],
    createdAt: message.createdAt,
    id: message.id,
    role: message.role,
  };
}
