import type { ThreadMessageLike } from "@assistant-ui/react";

import type { EvidentChatMessage } from "@/lib/types";

function toMessageStatus(
  status: EvidentChatMessage["status"]
): ThreadMessageLike["status"] {
  switch (status) {
    case "running":
      return { type: "running" };
    case "complete":
      return { reason: "stop", type: "complete" };
    case "error":
      return { reason: "error", type: "incomplete" };
    default:
      return { reason: "stop", type: "complete" };
  }
}

export function convertEvidentMessage(
  message: EvidentChatMessage
): ThreadMessageLike {
  const customMetadata = {
    generating: message.generating,
    hopProgress: message.hopProgress,
    reasoningTrace: message.reasoningTrace,
    route: message.route,
    subQueries: message.subQueries,
  };
  const hasCustomMetadata = Object.values(customMetadata).some(
    (value) => value !== undefined
  );

  return {
    content: message.contentParts as ThreadMessageLike["content"],
    createdAt: message.createdAt,
    id: message.id,
    ...(hasCustomMetadata && {
      metadata: {
        custom: customMetadata,
      },
    }),
    role: message.role,
    ...(message.role === "assistant" && {
      status: toMessageStatus(message.status),
    }),
  };
}
