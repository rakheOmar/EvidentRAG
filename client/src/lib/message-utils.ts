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
  return {
    content: message.contentParts as ThreadMessageLike["content"],
    createdAt: message.createdAt,
    id: message.id,
    role: message.role,
    ...(message.role === "assistant" && {
      status: toMessageStatus(message.status),
    }),
  };
}
