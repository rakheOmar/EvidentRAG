import { describe, expect, it } from "vitest";

import {
  hasRichMarkdown,
  isSegmentHighlighted,
  joinMarkdownSegments,
  requiresFullWidthHighlight,
} from "@/lib/markdown";

describe("hasRichMarkdown", () => {
  it.each([
    ["heading", "## Input representation\n\nE_i = E_t + E_s"],
    ["list", "- token embeddings"],
    ["table", "| Type | Purpose |\n|---|---|"],
    ["inline math", "For token \\(i\\), use \\(E_i\\)."],
  ])("detects %s", (_label, markdown) => {
    expect(hasRichMarkdown(markdown)).toBe(true);
  });

  it("keeps ordinary cited prose on the inline citation path", () => {
    expect(
      hasRichMarkdown("BERT sums token, segment, and position embeddings.")
    ).toBe(false);
  });
});

describe("joinMarkdownSegments", () => {
  it("separates structural segments without swallowing a following paragraph", () => {
    expect(
      joinMarkdownSegments([
        "## Figure 2",
        "| Type | Purpose |\n|---|---|\n| Token | Meaning |\n",
        "**Figure 2:** Input embeddings are summed.",
      ])
    ).toBe(
      "## Figure 2\n\n" +
        "| Type | Purpose |\n|---|---|\n| Token | Meaning |\n\n" +
        "**Figure 2:** Input embeddings are summed."
    );
  });

  it.each([
    [["", "", ""], ""],
    [["First", "second"], "First second"],
    [["- one", "- two"], "- one\n- two"],
  ] as const)("joins %j as %j", (parts, expected) => {
    expect(joinMarkdownSegments(parts)).toBe(expected);
  });
});

describe("isSegmentHighlighted", () => {
  it.each([
    [["ev-1", "ev-2"], "ev-2", [], true],
    [["ev-1"], "ev-2", ["ev-1"], false],
    [["ev-1"], null, ["ev-1"], true],
    [["ev-1"], null, [], false],
  ] as const)("returns %s for evidence=%j hovered=%s selected=%j", (evidenceIds, hoveredEvidenceId, selectedEvidenceIds, expected) => {
    expect(
      isSegmentHighlighted(evidenceIds, hoveredEvidenceId, selectedEvidenceIds)
    ).toBe(expected);
  });
});

describe("requiresFullWidthHighlight", () => {
  it.each([
    "| Type | Purpose |",
    "$$\nE_i = E_t + E_s\n$$",
    "1. Tokenize",
    "```python",
  ])("keeps structural Markdown full width: %s", (markdown) => {
    expect(requiresFullWidthHighlight(markdown)).toBe(true);
  });

  it.each([
    "For token \\(i\\), use \\(E_i\\).",
    "## Figure 2",
    "plain prose",
  ])("keeps %s tight to its content", (markdown) => {
    expect(requiresFullWidthHighlight(markdown)).toBe(false);
  });
});
