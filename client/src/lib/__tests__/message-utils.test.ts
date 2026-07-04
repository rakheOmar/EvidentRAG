import type { ThreadMessageLike } from "@assistant-ui/react";
import { describe, expect, it } from "vitest";

import { convertEvidentMessage } from "@/lib/message-utils";
import type { AnswerDetail, EvidentChatMessage } from "@/lib/types";

const makeUserMessage = (
  overrides: Partial<EvidentChatMessage> = {}
): EvidentChatMessage => ({
  content: "What is EvidentRAG?",
  createdAt: new Date("2026-07-04T10:00:00Z"),
  id: "user-1",
  role: "user",
  status: "complete",
  ...overrides,
});

const makeAssistantMessage = (
  overrides: Partial<EvidentChatMessage> = {}
): EvidentChatMessage => ({
  content: "",
  createdAt: new Date("2026-07-04T10:00:01Z"),
  id: "assistant-1",
  phase: "routing",
  role: "assistant",
  route: "simple",
  status: "running",
  ...overrides,
});

const makeAnswer = (overrides: Partial<AnswerDetail> = {}): AnswerDetail => ({
  evidence: [
    {
      content: "ERM boosts Evidence that grounded strong past Answers.",
      context_header: "Section 2",
      document_slug: "erm-paper",
      document_title: "ERM Paper",
      id: "e-1",
      page: 4,
    },
  ],
  full_text: "ERM boosts relevant Evidence based on prior outcomes.",
  id: "answer-1",
  query_id: "query-1",
  sentences: [
    {
      evidence_ids: ["e-1"],
      sentence_index: 0,
      sentence_text: "ERM boosts relevant Evidence based on prior outcomes.",
    },
  ],
  ...overrides,
});

describe("convertEvidentMessage", () => {
  it("converts a user Query into a text-only thread message", () => {
    const message = makeUserMessage();

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [{ text: "What is EvidentRAG?", type: "text" }],
      createdAt: new Date("2026-07-04T10:00:00Z"),
      id: "user-1",
      role: "user",
    });
  });

  it("converts a routing assistant message into a reasoning part", () => {
    const message = makeAssistantMessage();

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [
        { text: "Routing Query via the Simple Route...", type: "reasoning" },
      ],
      createdAt: new Date("2026-07-04T10:00:01Z"),
      id: "assistant-1",
      role: "assistant",
      status: { type: "running" },
    });
  });

  it("converts a generating assistant message into accumulated text parts", () => {
    const message = makeAssistantMessage({
      content: "Evidence Retrieval Memory improves retrieval.",
      phase: "generating",
      streamedSentences: ["Evidence Retrieval Memory improves retrieval."],
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [
        {
          text: "Evidence Retrieval Memory improves retrieval.",
          type: "text",
        },
      ],
      createdAt: new Date("2026-07-04T10:00:01Z"),
      id: "assistant-1",
      role: "assistant",
      status: { type: "running" },
    });
  });

  it("converts a completed assistant Answer into text and source parts", () => {
    const message = makeAssistantMessage({
      answer: makeAnswer(),
      content: "ERM boosts relevant Evidence based on prior outcomes.",
      phase: "done",
      status: "complete",
    });

    const result = convertEvidentMessage(message);

    expect(result).toEqual<ThreadMessageLike>({
      content: [
        {
          text: "ERM boosts relevant Evidence based on prior outcomes.",
          type: "text",
        },
        {
          filename: "erm-paper",
          id: "e-1",
          mediaType: "text/plain",
          providerMetadata: {
            evidentrag: { contextHeader: "Section 2", page: 4 },
          },
          sourceType: "document",
          title: "ERM Paper",
          type: "source",
        },
      ],
      createdAt: new Date("2026-07-04T10:00:01Z"),
      id: "assistant-1",
      role: "assistant",
      status: { type: "complete", reason: "stop" },
    });
  });
});
