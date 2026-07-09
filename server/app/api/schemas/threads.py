from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ThreadCreate(BaseModel):
    content: str


class MessageCreate(BaseModel):
    content: str


class ThreadSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    summary: str
    created_at: datetime
    updated_at: datetime


class SegmentResponse(BaseModel):
    id: UUID
    segment_index: int
    text: str
    evidence_ids: list[UUID]
    rating: Literal["up", "down"] | None = None


class EvidenceResponse(BaseModel):
    id: UUID
    content: str
    context_header: str
    document_title: str
    document_slug: str
    page: int
    erm_state: Literal["boost", "penalty"] | None = None
    erm_multiplier: float | None = None


class AnswerResponse(BaseModel):
    id: UUID
    message_id: UUID
    full_text: str
    reasoning_trace: list[dict[str, object]] = []
    segments: list[SegmentResponse]
    evidence: list[EvidenceResponse]
    content_parts: list[dict[str, object]] | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    reply_to_message_id: UUID | None
    position: int
    role: str
    content_text: str
    status: str
    selected_route: str | None
    sub_queries: list[str]
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    answer: AnswerResponse | None = None


class ThreadDetailResponse(ThreadSummaryResponse):
    messages: list[MessageResponse]


class ThreadTurnResponse(BaseModel):
    thread: ThreadSummaryResponse
    user_message: MessageResponse
    assistant_message: MessageResponse


class SentenceTraceFeedbackRequest(BaseModel):
    rating: Literal["up", "down"]


class SentenceTraceFeedbackResponse(BaseModel):
    rating: Literal["up", "down"]
    trace_id: UUID
