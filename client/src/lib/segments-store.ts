import type { Segment } from "@/lib/types";

const store = new Map<string, Segment[]>();

export function setMessageSegments(messageId: string, segments: Segment[]) {
  store.set(messageId, segments);
}

export function getMessageSegments(messageId: string): Segment[] | null {
  return store.get(messageId) ?? null;
}
