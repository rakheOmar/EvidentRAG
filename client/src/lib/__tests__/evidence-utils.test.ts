import { describe, expect, it } from "vitest";
import { buildEvidenceIndexMap } from "@/lib/evidence-utils";
import type { SentenceTrace } from "@/lib/types";

const makeSentence = (
  sentence_index: number,
  sentence_text: string,
  evidence_ids: string[]
): SentenceTrace => ({
  evidence_ids,
  sentence_index,
  sentence_text,
});

describe("buildEvidenceIndexMap", () => {
  it("returns an empty map when there are no sentences", () => {
    const sentences: SentenceTrace[] = [];
    expect(buildEvidenceIndexMap(sentences)).toEqual(new Map<string, number>());
  });

  it("assigns first-appearance indices and reuses them for shared evidence", () => {
    const sentences = [
      makeSentence(0, "First.", ["e-1", "e-2"]),
      makeSentence(1, "Second.", ["e-2", "e-3"]),
      makeSentence(2, "Third.", ["e-1", "e-3"]),
    ];
    const map = buildEvidenceIndexMap(sentences);
    expect(map.get("e-1")).toBe(1);
    expect(map.get("e-2")).toBe(2);
    expect(map.get("e-3")).toBe(3);
  });
});
