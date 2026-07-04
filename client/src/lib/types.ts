export type QueryStatus = "pending" | "running" | "completed" | "failed";

export type QueryRoute = "simple";

export interface QuerySummary {
  completed_at: string | null;
  created_at: string;
  error_message: string | null;
  id: string;
  query_text: string;
  selected_route: QueryRoute | null;
  status: QueryStatus;
  updated_at: string;
}

export interface SentenceTrace {
  evidence_ids: string[];
  sentence_index: number;
  sentence_text: string;
}

export interface Evidence {
  content: string;
  context_header: string | null;
  document_slug: string | null;
  document_title: string | null;
  id: string;
  page: number | null;
}

export interface AnswerDetail {
  evidence: Evidence[];
  full_text: string;
  id: string;
  query_id: string;
  sentences: SentenceTrace[];
}

export interface RouteSelectedEvent {
  route: QueryRoute;
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
    Array.isArray(obj.sentences)
  );
}

export interface DoneEvent extends AnswerDetail {}

export interface ErrorEvent {
  message: string;
}

export interface EvidentChatMessage {
  answer?: AnswerDetail | null;
  content: string;
  createdAt: Date;
  errorMessage?: string | null;
  id: string;
  phase?: "routing" | "retrieving" | "generating" | "done" | "error";
  queryId?: string | null;
  role: "assistant" | "user";
  route?: QueryRoute | null;
  status: "running" | "complete" | "error";
  streamedSentences?: string[];
}
