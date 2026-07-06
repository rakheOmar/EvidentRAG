"use client";

import { type FC, useCallback, useMemo, useState } from "react";

import type { Segment } from "@/lib/types";

interface BadgeEntry {
  num: number;
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
        entries.push({ num, segmentIndices: indices });
      } else {
        const entry = entries.find((e) => e.num === num);
        if (entry) {
          entry.segmentIndices.add(seg.segment_index);
        }
      }
    }
  }

  return entries;
}

function Badge({
  num,
  onHover,
  onLeave,
}: {
  num: number;
  onHover: () => void;
  onLeave: () => void;
}) {
  return (
    <button
      className="ms-0.5 inline-flex cursor-pointer items-center justify-center rounded-xl bg-muted px-2.5 py-0.5 font-medium text-[11px] text-muted-foreground leading-none"
      onBlur={onLeave}
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
  const [hovered, setHovered] = useState<number | null>(null);

  const badgeEntries = useMemo(() => buildBadgeEntries(segments), [segments]);

  const clearHover = useCallback(() => setHovered(null), []);

  return (
    <fieldset
      className="group inline items-center gap-1"
      onBlur={clearHover}
      onMouseLeave={clearHover}
    >
      {segments.map((seg) => {
        const isHighlighted =
          hovered !== null &&
          badgeEntries
            .filter((e) => e.num === hovered)
            .some((e) => e.segmentIndices.has(seg.segment_index));

        return (
          <span
            className={
              isHighlighted
                ? "rounded bg-muted px-1 transition-colors"
                : "px-1 transition-colors"
            }
            key={seg.segment_index}
          >
            {seg.text}
          </span>
        );
      })}
      {badgeEntries.length > 0 && (
        <span className="ms-1">
          {badgeEntries.map(({ num }) => (
            <Badge
              key={num}
              num={num}
              onHover={() => setHovered(num)}
              onLeave={clearHover}
            />
          ))}
        </span>
      )}
    </fieldset>
  );
};
