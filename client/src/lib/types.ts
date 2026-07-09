import type { ThreadAssistantMessagePart } from "@assistant-ui/react";

export type QueryStatus = "pending" | "running" | "completed" | "failed";

export type QueryRoute = "simple" | "multi_hop" | "comparison" | "aggregation";

export interface QuerySummary {
  completed_at: string | null;
  created_at: string;
  error_message: string | null;
  id: string;
  query_text: string;
  selected_route: QueryRoute | null;
  status: QueryStatus;
  sub_queries?: string[];
  updated_at: string;
}

export interface Segment {
  evidence_ids: string[];
  segment_index: number;
  text: string;
}

export interface Evidence {
  content: string;
  context_header: string | null;
  document_slug: string | null;
  document_title: string | null;
  id: string;
  page: number | null;
}

export interface ReasoningTraceStep {
  text: string;
  type: "step";
}

export interface ReasoningTraceHop {
  hop: number;
  intermediate_answer: string;
  sub_query: string;
  type: "hop";
}

export interface ReasoningTraceCandidate {
  document_title: string;
  evidence_id: string;
  page: number;
  snippet: string;
}

export interface ReasoningTraceRetrieval {
  candidates: ReasoningTraceCandidate[];
  label: string;
  type: "retrieval";
}

export type ReasoningTraceEntry =
  | ReasoningTraceStep
  | ReasoningTraceHop
  | ReasoningTraceRetrieval;

export interface AnswerDetail {
  evidence: Evidence[];
  full_text: string;
  id: string;
  query_id: string;
  reasoning_trace?: ReasoningTraceEntry[];
  segments: Segment[];
}

export interface RouteSelectedEvent {
  route: QueryRoute;
  sub_queries: string[];
}

export interface HopProgressEvent {
  hop: number;
  intermediate_answer: string;
  sub_query: string;
}

export interface RetrievingEvent {
  status: "retrieving";
}

export interface GeneratingEvent {
  sentence: string;
}

export interface PendingAnswerResponse {
  status: string;
}

export type QueryAnswerResponse = AnswerDetail | PendingAnswerResponse;

export function isAnswerDetail(value: unknown): value is AnswerDetail {
  if (value === null || value === undefined || typeof value !== "object") {
    return false;
  }
  const obj = value as Record<string, unknown>;
  return (
    typeof obj.full_text === "string" &&
    Array.isArray(obj.evidence) &&
    Array.isArray(obj.segments)
  );
}

export interface DoneEvent extends AnswerDetail {}

export interface ErrorEvent {
  message: string;
}

export interface ContentPartsEvent {
  parts: ThreadAssistantMessagePart[];
}

export interface DoneEventWithContentParts {
  content_parts: ThreadAssistantMessagePart[];
  error: boolean;
  error_message?: string;
  query_id: string;
  reasoning_trace?: ReasoningTraceEntry[];
  segments?: Segment[];
}

export interface EvidentChatMessage {
  contentParts: ThreadAssistantMessagePart[];
  createdAt: Date;
  generating?: boolean;
  hopProgress?: HopProgressEvent[];
  id: string;
  queryId?: string | null;
  reasoningTrace?: ReasoningTraceEntry[];
  role: "assistant" | "user";
  route?: QueryRoute;
  status: "running" | "complete" | "error";
  subQueries?: string[];
}
