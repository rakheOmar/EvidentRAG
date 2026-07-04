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
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class SentenceTraceResponse(BaseModel):
    sentence_index: int
    sentence_text: str
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
    sentences: list[SentenceTraceResponse]
    evidence: list[EvidenceResponse]


class PendingAnswerResponse(BaseModel):
    status: str
