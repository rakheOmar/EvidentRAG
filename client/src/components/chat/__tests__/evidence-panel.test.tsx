import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidencePanel } from "@/components/chat/evidence-panel";
import type { AnswerDetail } from "@/lib/types";

function makeBrokenAnswer(): AnswerDetail {
  return {
    evidence: undefined as unknown as AnswerDetail["evidence"],
    full_text: "Answer without Evidence array.",
    id: "answer-1",
    query_id: "query-1",
    sentences: [],
  };
}

describe("EvidencePanel", () => {
  it("falls back to the empty state when the Answer has no Evidence array", () => {
    render(
      <EvidencePanel answer={makeBrokenAnswer()} selectedEvidenceId="e-1" />
    );

    expect(
      screen.getByText("Evidence for the current Answer will appear here.")
    ).toBeInTheDocument();
  });
});
