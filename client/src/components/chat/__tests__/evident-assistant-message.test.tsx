import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PropsWithChildren, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  EvidenceSelectionProvider,
  useEvidenceSelection,
} from "@/components/chat/evidence-selection";
import { EvidentAssistantMessage } from "@/components/chat/evident-assistant-message";
import { EvidentMessagesProvider } from "@/components/chat/evident-messages";
import type { AnswerDetail, EvidentChatMessage } from "@/lib/types";

const openEvidenceButtonName = /open evidence/i;

vi.mock("@assistant-ui/react", () => ({
  MessagePrimitive: {
    Error: () => null,
    Parts: () => <div data-testid="assistant-parts-fallback" />,
    Root: ({ children }: PropsWithChildren) => <div>{children}</div>,
  },
  useAuiState: (selector: (state: { message: { id: string } }) => ReactNode) =>
    selector({ message: { id: "assistant-1" } }),
}));

vi.mock("@/components/assistant-ui/reasoning", () => ({
  ReasoningContent: ({ children }: PropsWithChildren) => <div>{children}</div>,
  ReasoningRoot: ({ children }: PropsWithChildren) => <div>{children}</div>,
  ReasoningText: ({ children }: PropsWithChildren) => <div>{children}</div>,
  ReasoningTrigger: () => null,
}));

function makeBrokenAnswer(): AnswerDetail {
  return {
    evidence: [],
    full_text: "Completed Answer without Sentence Traces.",
    id: "answer-1",
    query_id: "query-1",
    sentences: undefined as unknown as AnswerDetail["sentences"],
  };
}

function makeAnswerWithSentenceTraces(): AnswerDetail {
  return {
    evidence: [
      {
        content: "Citations come from Sentence Traces.",
        context_header: "Section 1",
        document_slug: "citations-doc",
        document_title: "Citations Doc",
        id: "e-1",
        page: 2,
      },
    ],
    full_text: "Citations come from Sentence Traces.",
    id: "answer-2",
    query_id: "query-2",
    sentences: [
      {
        evidence_ids: ["e-1"],
        sentence_index: 0,
        sentence_text: "Citations come from Sentence Traces.",
      },
    ],
  };
}

function makeAssistantMessage(
  overrides: Partial<EvidentChatMessage> = {}
): EvidentChatMessage {
  return {
    answer: makeBrokenAnswer(),
    content: "Completed Answer without Sentence Traces.",
    createdAt: new Date("2026-07-04T10:00:00Z"),
    id: "assistant-1",
    phase: "done",
    role: "assistant",
    status: "complete",
    ...overrides,
  };
}

function SelectedEvidenceProbe() {
  const { selectedEvidenceId } = useEvidenceSelection();

  return (
    <div data-testid="selected-evidence">{selectedEvidenceId ?? "none"}</div>
  );
}

describe("EvidentAssistantMessage", () => {
  it("falls back to plain Answer text when sentence traces are missing", () => {
    render(
      <EvidentMessagesProvider messages={[makeAssistantMessage()]}>
        <EvidenceSelectionProvider>
          <EvidentAssistantMessage />
        </EvidenceSelectionProvider>
      </EvidentMessagesProvider>
    );

    expect(
      screen.getByText("Completed Answer without Sentence Traces.")
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: openEvidenceButtonName })
    ).not.toBeInTheDocument();
  });

  it("renders a waiting fallback when assistant content is missing", () => {
    render(
      <EvidentMessagesProvider
        messages={[
          makeAssistantMessage({
            answer: undefined,
            content: undefined as unknown as EvidentChatMessage["content"],
            phase: "generating",
          }),
        ]}
      >
        <EvidenceSelectionProvider>
          <EvidentAssistantMessage />
        </EvidenceSelectionProvider>
      </EvidentMessagesProvider>
    );

    expect(screen.getByText("Waiting for the Answer...")).toBeInTheDocument();
  });

  it("renders citation badges and selects Evidence when clicked", async () => {
    const user = userEvent.setup();

    render(
      <EvidentMessagesProvider
        messages={[
          makeAssistantMessage({
            answer: makeAnswerWithSentenceTraces(),
            content: "Citations come from Sentence Traces.",
          }),
        ]}
      >
        <EvidenceSelectionProvider>
          <EvidentAssistantMessage />
          <SelectedEvidenceProbe />
        </EvidenceSelectionProvider>
      </EvidentMessagesProvider>
    );

    await user.click(screen.getByRole("button", { name: "Open Evidence 1" }));

    expect(screen.getByTestId("selected-evidence")).toHaveTextContent("e-1");
  });
});
