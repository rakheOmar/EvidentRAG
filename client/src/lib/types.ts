import type { ThreadAssistantMessagePart } from "@assistant-ui/react";

export type MessageStatus = "pending" | "running" | "completed" | "failed";

export type QueryRoute =
	| "simple"
	| "multi_hop"
	| "comparison"
	| "aggregation"
	| "conversation";

export interface ThreadSummary {
	created_at: string;
	id: string;
	summary: string;
	title: string;
	updated_at: string;
}

export interface Segment {
	evidence_ids: string[];
	id: string;
	rating: "up" | "down" | null;
	segment_index: number;
	text: string;
}

export interface Evidence {
	asset_key?: string | null;
	asset_url?: string | null;
	bounding_box?: Record<string, number> | null;
	content: string;
	context_header: string | null;
	document_slug: string | null;
	document_title: string | null;
	erm_multiplier: number | null;
	erm_state: "boost" | "penalty" | null;
	id: string;
	kind?: string;
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
	content_parts?: ThreadAssistantMessagePart[];
	context_usage?: ContextUsage | null;
	evidence: Evidence[];
	full_text: string;
	id: string;
	message_id: string;
	reasoning_trace?: ReasoningTraceEntry[];
	segments: Segment[];
}

export interface ContextUsage {
	completion_tokens: number;
	estimated: boolean;
	prompt_tokens: number;
	total_tokens: number;
}

export interface ThreadMessage {
	answer?: AnswerDetail | null;
	completed_at: string | null;
	content_text: string;
	created_at: string;
	error_message: string | null;
	id: string;
	position: number;
	reply_to_message_id: string | null;
	role: "assistant" | "user";
	selected_route: QueryRoute | null;
	status: MessageStatus;
	sub_queries: string[];
	thread_id: string;
	updated_at: string;
}

export interface ThreadDetail extends ThreadSummary {
	messages: ThreadMessage[];
}

export interface ThreadTurnResponse {
	assistant_message: ThreadMessage;
	thread: ThreadSummary;
	user_message: ThreadMessage;
}

export interface DocumentRecord {
	byte_size: number | null;
	created_at: string;
	document_id: string;
	error_message: string | null;
	id: string;
	is_current: boolean;
	original_filename: string | null;
	page_count: number;
	source_id: string;
	source_key: string;
	status: string;
	title: string;
	updated_at: string;
	version_number: number;
	warnings: unknown[];
}

export interface DocumentListResponse {
	items: DocumentRecord[];
	limit: number;
	offset: number;
	total: number;
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

export interface PendingAnswerResponse {
	status: string;
}

export interface DoneEventWithContentParts extends AnswerDetail {
	content_parts: ThreadAssistantMessagePart[];
	error: boolean;
	error_message?: string;
	message_id: string;
	thread_id: string;
}

export interface ContentPartsEvent {
	parts: ThreadAssistantMessagePart[];
}

export interface SentenceTraceFeedbackResponse {
	rating: "up" | "down";
	trace_id: string;
}

export interface EvidentChatMessage {
	contentParts: ThreadAssistantMessagePart[];
	contextUsage?: ContextUsage;
	createdAt: Date;
	generating?: boolean;
	hopProgress?: HopProgressEvent[];
	id: string;
	messageId?: string | null;
	reasoningTrace?: ReasoningTraceEntry[];
	role: "assistant" | "user";
	route?: QueryRoute;
	status: "running" | "complete" | "error";
	subQueries?: string[];
	threadId?: string | null;
}
