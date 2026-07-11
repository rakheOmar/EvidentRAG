from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: UUID
    document_id: UUID
    source_id: UUID
    source_key: str
    title: str
    version_number: int
    status: str
    is_current: bool
    original_filename: str | None
    page_count: int
    byte_size: int | None
    warnings: list = Field(default_factory=list)
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    limit: int
    offset: int
    total: int
