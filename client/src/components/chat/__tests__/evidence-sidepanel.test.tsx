import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  EvidencePanelProvider,
  useEvidencePanel,
} from "@/components/chat/evidence-context";
import { EvidenceSidepanel } from "@/components/chat/evidence-sidepanel";

const DOCUMENT_ONE_BUTTON_NAME = /Document One/i;
const noop = () => undefined;

vi.mock("@/hooks/use-mobile", () => ({
  useIsMobile: () => false,
}));

beforeEach(() => {
  Element.prototype.getAnimations ??= () => [];
});

afterEach(() => {
  cleanup();
});

function EvidenceHarness() {
  const {
    clearEvidence,
    selectedEvidenceIds,
    selectedMessageId,
    selectEvidence,
  } = useEvidencePanel();

  return (
    <div>
      <button
        onClick={() => selectEvidence("message-1", ["ev-1"])}
        type="button"
      >
        seed selection
      </button>
      <button onClick={clearEvidence} type="button">
        clear selection
      </button>
      <output data-testid="selected-message">
        {selectedMessageId ?? "none"}
      </output>
      <output data-testid="selected-evidence">
        {selectedEvidenceIds.join(",") || "none"}
      </output>
      <EvidenceSidepanel
        activeEvidenceId={selectedEvidenceIds[0] ?? null}
        evidence={[
          {
            content: "First evidence",
            context_header: "Context",
            document_slug: "doc-1",
            document_title: "Document One",
            id: "ev-1",
            page: 1,
          },
          {
            content: "Second evidence",
            context_header: "Context",
            document_slug: "doc-1",
            document_title: "Document One",
            id: "ev-2",
            page: 2,
          },
        ]}
        onClose={noop}
        open
      />
    </div>
  );
}

describe("EvidenceSidepanel", () => {
  it("preserves the current message id when switching evidence items", () => {
    render(
      <EvidencePanelProvider>
        <EvidenceHarness />
      </EvidencePanelProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "seed selection" }));

    expect(screen.getByTestId("selected-message")).toHaveTextContent(
      "message-1"
    );
    expect(screen.getByTestId("selected-evidence")).toHaveTextContent("ev-1");

    const evidenceButtons = screen.getAllByRole("button", {
      name: DOCUMENT_ONE_BUTTON_NAME,
    });
    const secondEvidenceButton = evidenceButtons[1];
    expect(secondEvidenceButton).toBeDefined();
    if (!secondEvidenceButton) {
      throw new Error("Expected a second evidence button.");
    }

    fireEvent.click(secondEvidenceButton);

    expect(screen.getByTestId("selected-message")).toHaveTextContent(
      "message-1"
    );
    expect(screen.getByTestId("selected-evidence")).toHaveTextContent("ev-2");
  });

  it("clears evidence selection from the panel close action", () => {
    render(
      <EvidencePanelProvider>
        <EvidenceHarness />
      </EvidencePanelProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: "seed selection" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Close evidence panel" })
    );

    expect(screen.getByTestId("selected-message")).toHaveTextContent("none");
    expect(screen.getByTestId("selected-evidence")).toHaveTextContent("none");
  });
});
