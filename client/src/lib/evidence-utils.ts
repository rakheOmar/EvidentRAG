import type { SentenceTrace } from "@/lib/types";

export function buildEvidenceIndexMap(
  sentences: SentenceTrace[]
): Map<string, number> {
  const evidenceIndexMap = new Map<string, number>();
  let nextIndex = 1;
  for (const sentence of sentences) {
    for (const evidenceId of sentence.evidence_ids) {
      if (!evidenceIndexMap.has(evidenceId)) {
        evidenceIndexMap.set(evidenceId, nextIndex);
        nextIndex++;
      }
    }
  }
  return evidenceIndexMap;
}
