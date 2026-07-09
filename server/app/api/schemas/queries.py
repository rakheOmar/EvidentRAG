from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class QueryCreate(BaseModel):
    query_text: str


class QueryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    query_text: str
    selected_route: str
    sub_queries: list[str]
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class SegmentResponse(BaseModel):
    segment_index: int
    text: str
    evidence_ids: list[UUID]


class EvidenceResponse(BaseModel):
    id: UUID
    content: str
    context_header: str
    document_title: str
    document_slug: str
    page: int


class AnswerResponse(BaseModel):
    id: UUID
    query_id: UUID
    full_text: str
    reasoning_trace: list[dict[str, object]] = []
    segments: list[SegmentResponse]
    evidence: list[EvidenceResponse]
    content_parts: list[dict[str, object]] | None = None


class PendingAnswerResponse(BaseModel):
    status: str
