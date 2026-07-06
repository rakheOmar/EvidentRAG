import type { Evidence } from "@/lib/types";

const store = new Map<string, Evidence[]>();

export function setMessageEvidence(messageId: string, evidence: Evidence[]) {
  store.set(messageId, evidence);
}

export function getMessageEvidence(messageId: string): Evidence[] | null {
  return store.get(messageId) ?? null;
}
