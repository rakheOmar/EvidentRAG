import { describe, expect, it } from "vitest";

import {
  hasRichMarkdown,
  isSegmentHighlighted,
  joinMarkdownSegments,
  requiresFullWidthHighlight,
} from "@/lib/markdown";

describe("hasRichMarkdown", () => {
  it("detects Markdown that must be rendered instead of displayed as cited plain text", () => {
    expect(
      hasRichMarkdown("## Input representation\n\n\\(E_i\\) = E_t + E_s")
    ).toBe(true);
  });

  it("keeps ordinary cited prose on the inline citation path", () => {
    expect(
      hasRichMarkdown("BERT sums token, segment, and position embeddings.")
    ).toBe(false);
  });
});

describe("joinMarkdownSegments", () => {
  it("keeps a trailing table newline from swallowing the following paragraph", () => {
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
});

describe("isSegmentHighlighted", () => {
  it("highlights the traced segment for the hovered citation", () => {
    expect(isSegmentHighlighted(["ev-1", "ev-2"], "ev-2", [])).toBe(true);
    expect(isSegmentHighlighted(["ev-1"], "ev-2", ["ev-1"])).toBe(false);
  });

  it("falls back to the selected citation when none is hovered", () => {
    expect(isSegmentHighlighted(["ev-1"], null, ["ev-1"])).toBe(true);
  });
});

describe("requiresFullWidthHighlight", () => {
  it("keeps prose, inline math, and headings tight to their content", () => {
    expect(
      requiresFullWidthHighlight("For token \\(i\\), use \\(E_i\\).")
    ).toBe(false);
    expect(requiresFullWidthHighlight("## Figure 2")).toBe(false);
  });

  it.each([
    "| Type | Purpose |",
    "$$\nE_i = E_t + E_s\n$$",
    "1. Tokenize",
    "```python",
  ])("keeps structural Markdown full width: %s", (markdown) => {
    expect(requiresFullWidthHighlight(markdown)).toBe(true);
  });
});
