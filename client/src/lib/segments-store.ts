import type { Segment } from "@/lib/types";

const store = new Map<string, Segment[]>();

export function setMessageSegments(messageId: string, segments: Segment[]) {
  store.set(messageId, segments);
}

export function getMessageSegments(messageId: string): Segment[] | null {
  return store.get(messageId) ?? null;
}

export function updateSegmentRating(
  messageId: string,
  traceId: string,
  rating: Segment["rating"]
) {
  const segments = store.get(messageId);
  if (!segments) {
    return;
  }

  store.set(
    messageId,
    segments.map((segment) =>
      segment.id === traceId ? { ...segment, rating } : segment
    )
  );
}
