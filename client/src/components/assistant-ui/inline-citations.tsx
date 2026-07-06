"use client";

import { type FC, useCallback, useMemo, useRef, useState } from "react";
import type { Segment } from "@/lib/types";
import { useEvidencePanel } from "@/components/chat/evidence-context";

interface BadgeEntry {
  num: number;
  evidenceIds: string[];
  segmentIndices: Set<number>;
}

function buildBadgeEntries(segments: Segment[]) {
  const evidenceNumbers = new Map<string, number>();
  const entries: BadgeEntry[] = [];
  let next = 1;

  for (const seg of segments) {
    for (const id of seg.evidence_ids) {
      let num = evidenceNumbers.get(id);
      if (num === undefined) {
        num = next++;
        evidenceNumbers.set(id, num);
        const indices = new Set<number>();
        indices.add(seg.segment_index);
        entries.push({
          evidenceIds: [id],
          num,
          segmentIndices: indices,
        });
      } else {
        const entry = entries.find((e) => e.num === num);
        if (entry) {
          entry.segmentIndices.add(seg.segment_index);
          if (!entry.evidenceIds.includes(id)) {
            entry.evidenceIds.push(id);
          }
        }
      }
    }
  }

  return entries;
}

function Badge({
  active,
  num,
  onHover,
  onLeave,
  onSelect,
}: {
  active: boolean;
  num: number;
  onHover: () => void;
  onLeave: () => void;
  onSelect: () => void;
}) {
  return (
    <button
      className={
        active
          ? "ms-0.5 inline-flex cursor-pointer items-center justify-center rounded-xl bg-primary px-2.5 py-0.5 font-medium text-[11px] text-primary-foreground leading-none"
          : "ms-0.5 inline-flex cursor-pointer items-center justify-center rounded-xl bg-muted px-2.5 py-0.5 font-medium text-[11px] text-muted-foreground leading-none hover:bg-muted/80"
      }
      onBlur={onLeave}
      onClick={onSelect}
      onFocus={onHover}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      type="button"
    >
      {num}
    </button>
  );
}

export const InlineCitations: FC<{ segments: Segment[] }> = ({ segments }) => {
  const [hoveredBadge, setHoveredBadge] = useState<number | null>(null);
  const { selectedEvidenceIds, selectEvidence, clearEvidence } =
    useEvidencePanel();
  const prevIdsRef = useRef(selectedEvidenceIds);

  const selectedEvidenceSet = useMemo(
    () => new Set(selectedEvidenceIds),
    [selectedEvidenceIds]
  );

  const badgeEntries = useMemo(() => buildBadgeEntries(segments), [segments]);

  const clearHover = useCallback(() => setHoveredBadge(null), []);

  const handleBadgeSelect = useCallback(
    (entry: BadgeEntry) => {
      if (selectedEvidenceIds.length > 0) {
        const sameSelection =
          entry.evidenceIds.length === selectedEvidenceIds.length &&
          entry.evidenceIds.every((id) => selectedEvidenceIds.includes(id));
        if (sameSelection && prevIdsRef.current === selectedEvidenceIds) {
          clearEvidence();
          return;
        }
      }
      prevIdsRef.current = entry.evidenceIds;
      selectEvidence(entry.evidenceIds);
    },
    [clearEvidence, selectEvidence, selectedEvidenceIds]
  );

  const isSegmentHighlighted = useCallback(
    (seg: Segment) => {
      if (hoveredBadge !== null) {
        return badgeEntries
          .filter((e) => e.num === hoveredBadge)
          .some((e) => e.segmentIndices.has(seg.segment_index));
      }
      return seg.evidence_ids.some((id) => selectedEvidenceSet.has(id));
    },
    [hoveredBadge, badgeEntries, selectedEvidenceSet]
  );

  return (
    <div className="group inline items-center gap-1">
      {segments.map((seg) => (
        <span
          className={
            isSegmentHighlighted(seg)
              ? "rounded bg-primary/10 px-1 transition-colors"
              : "px-1 transition-colors"
          }
          key={seg.segment_index}
        >
          {seg.text}
        </span>
      ))}
      {badgeEntries.length > 0 && (
        <span className="ms-1">
          {badgeEntries.map(({ evidenceIds, num, segmentIndices }) => (
            <Badge
              key={num}
              active={evidenceIds.some((id) => selectedEvidenceSet.has(id))}
              num={num}
              onHover={() => setHoveredBadge(num)}
              onLeave={clearHover}
              onSelect={() => handleBadgeSelect({ evidenceIds, num, segmentIndices })}
            />
          ))}
        </span>
      )}
    </div>
  );
};
