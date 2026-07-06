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
  contentParts: [{ type: "text", text: "Hello world." }],
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
        { type: "text", text: "RAG combines retrieval with generation." },
      ],
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [
        { type: "text", text: "RAG combines retrieval with generation." },
      ],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "msg-1",
      role: "assistant",
      status: { type: "complete", reason: "stop" },
    });
  });

  it("passes reasoning parts through as-is", () => {
    const message = makeMessage({
      contentParts: [{ type: "reasoning", text: "Routing Query..." }],
      status: "running",
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [{ type: "reasoning", text: "Routing Query..." }],
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
          type: "source",
          sourceType: "document",
          id: "ev-1",
          title: "RAG Paper",
          mediaType: "text/plain",
          providerMetadata: { evidentrag: { page: 3 } },
        },
      ],
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [
        {
          type: "source",
          sourceType: "document",
          id: "ev-1",
          title: "RAG Paper",
          mediaType: "text/plain",
          providerMetadata: { evidentrag: { page: 3 } },
        },
      ],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "msg-1",
      role: "assistant",
      status: { type: "complete", reason: "stop" },
    });
  });

  it("passes mixed content parts through as-is", () => {
    const parts: ThreadAssistantMessagePart[] = [
      { type: "reasoning", text: "Generating Answer..." },
      { type: "text", text: "RAG stands for Retrieval Augmented Generation." },
      {
        type: "source",
        sourceType: "document",
        id: "ev-1",
        title: "RAG Paper",
        mediaType: "text/plain",
      },
    ];
    const message = makeMessage({ contentParts: parts, status: "complete" });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: parts,
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "msg-1",
      role: "assistant",
      status: { type: "complete", reason: "stop" },
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

    expect(result.status).toEqual({ type: "incomplete", reason: "error" });
  });

  it("converts a user message without status", () => {
    const message: EvidentChatMessage = {
      contentParts: [{ type: "text", text: "What is RAG?" }],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "user-1",
      role: "user",
      status: "complete",
    };

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [{ type: "text", text: "What is RAG?" }],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "user-1",
      role: "user",
    });
  });
});
