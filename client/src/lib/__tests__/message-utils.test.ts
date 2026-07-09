import type {
  ThreadAssistantMessagePart,
  ThreadMessageLike,
} from "@assistant-ui/react";
import { describe, expect, it } from "vitest";

import { convertEvidentMessage } from "@/lib/message-utils";
import type { EvidentChatMessage } from "@/lib/types";

const makeMessage = (
  overrides: Partial<EvidentChatMessage> = {}
): EvidentChatMessage => ({
  contentParts: [{ text: "Hello world.", type: "text" }],
  createdAt: new Date("2026-07-04T10:00:00Z"),
  id: "msg-1",
  role: "assistant",
  status: "complete",
  ...overrides,
});

describe("convertEvidentMessage", () => {
  it("passes text parts through as-is", () => {
    const message = makeMessage({
      contentParts: [
        { text: "RAG combines retrieval with generation.", type: "text" },
      ],
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [
        { text: "RAG combines retrieval with generation.", type: "text" },
      ],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "msg-1",
      role: "assistant",
      status: { reason: "stop", type: "complete" },
    });
  });

  it("passes reasoning parts through as-is", () => {
    const message = makeMessage({
      contentParts: [{ text: "Routing Query...", type: "reasoning" }],
      status: "running",
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [{ text: "Routing Query...", type: "reasoning" }],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "msg-1",
      role: "assistant",
      status: { type: "running" },
    });
  });

  it("passes source parts through as-is", () => {
    const message = makeMessage({
      contentParts: [
        {
          id: "ev-1",
          mediaType: "text/plain",
          providerMetadata: { evidentrag: { page: 3 } },
          sourceType: "document",
          title: "RAG Paper",
          type: "source",
        },
      ],
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [
        {
          id: "ev-1",
          mediaType: "text/plain",
          providerMetadata: { evidentrag: { page: 3 } },
          sourceType: "document",
          title: "RAG Paper",
          type: "source",
        },
      ],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "msg-1",
      role: "assistant",
      status: { reason: "stop", type: "complete" },
    });
  });

  it("passes mixed content parts through as-is", () => {
    const parts: ThreadAssistantMessagePart[] = [
      { text: "Generating Answer...", type: "reasoning" },
      { text: "RAG stands for Retrieval Augmented Generation.", type: "text" },
      {
        id: "ev-1",
        mediaType: "text/plain",
        sourceType: "document",
        title: "RAG Paper",
        type: "source",
      },
    ];
    const message = makeMessage({ contentParts: parts, status: "complete" });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: parts,
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "msg-1",
      role: "assistant",
      status: { reason: "stop", type: "complete" },
    });
  });

  it("maps running status correctly", () => {
    const message = makeMessage({ status: "running" });

    const result = convertEvidentMessage(message);

    expect(result.status).toEqual({ type: "running" });
  });

  it("maps error status correctly", () => {
    const message = makeMessage({ status: "error" });

    const result = convertEvidentMessage(message);

    expect(result.status).toEqual({ reason: "error", type: "incomplete" });
  });

  it("converts a user message without status", () => {
    const message: EvidentChatMessage = {
      contentParts: [{ text: "What is RAG?", type: "text" }],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "user-1",
      role: "user",
      status: "complete",
    };

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [{ text: "What is RAG?", type: "text" }],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "user-1",
      role: "user",
    });
  });
});
