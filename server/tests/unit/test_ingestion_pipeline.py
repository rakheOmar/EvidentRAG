from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.application.ingestion.pipeline import (
    DocumentIngestionPipeline,
    _canonical_document_query,
    _extract_structured_chunks,
    _nearest_text_chunk_index,
)


class _Redis:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.messages.append((channel, message))


class _SessionContext:
    def __init__(self, document) -> None:
        self.document = document

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def get(self, model, document_id):
        return self.document

    async def commit(self) -> None:
        pass


@pytest.mark.asyncio
async def test_ingestion_progress_events_are_structured_and_correlated() -> None:
    redis = _Redis()
    pipeline = DocumentIngestionPipeline(
        session_factory=None,
        redis=redis,
        embedding_client=None,
        llm_client=None,
        qdrant_store=None,
        storage=None,
    )
    document_id = uuid4()

    await pipeline._publish(document_id, "embedding", 45, evidence_count=12)

    assert redis.messages[0][0] == f"document:{document_id}:events"
    event = json.loads(redis.messages[0][1])
    assert event == {
        "event": "progress",
        "data": {
            "document_id": str(document_id),
            "stage": "embedding",
            "progress": 45,
            "evidence_count": 12,
        },
    }


def test_deduplication_query_excludes_the_upload_source() -> None:
    source_id = uuid4()
    statement = _canonical_document_query("hash", source_id)

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "documents.source_id != %(source_id_1)s" in sql


def test_structured_chunks_carry_document_and_section_context() -> None:
    chunks = _extract_structured_chunks(
        "# Handbook\n\n## Access\n\nUsers may request access through the portal.",
        "Security Guide",
    )

    assert len(chunks) == 1
    assert chunks[0].content == "Users may request access through the portal."
    assert chunks[0].context_header == (
        "Passage from Security Guide, section Handbook > Access."
    )


def test_visuals_are_associated_with_nearest_text_chunk_by_source_order() -> None:
    assert _nearest_text_chunk_index(0, text_count=4, visual_count=2) == 0
    assert _nearest_text_chunk_index(1, text_count=4, visual_count=2) == 2
    assert _nearest_text_chunk_index(0, text_count=0, visual_count=2) is None


@pytest.mark.asyncio
async def test_ready_ingestion_repairs_qdrant_eligibility_without_reingesting() -> None:
    document_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        status="ready",
        is_current=True,
    )
    qdrant = _Qdrant()
    pipeline = DocumentIngestionPipeline(
        session_factory=lambda: _SessionContext(document),
        redis=_Redis(),
        embedding_client=None,
        llm_client=None,
        qdrant_store=qdrant,
        storage=None,
    )

    await pipeline.run(str(document_id))

    assert qdrant.eligibility_calls == [(str(document_id), True)]


@pytest.mark.asyncio
async def test_ready_historical_ingestion_stays_ineligible() -> None:
    document_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        status="ready",
        is_current=False,
    )
    qdrant = _Qdrant()
    pipeline = DocumentIngestionPipeline(
        session_factory=lambda: _SessionContext(document),
        redis=_Redis(),
        embedding_client=None,
        llm_client=None,
        qdrant_store=qdrant,
        storage=None,
    )

    await pipeline.run(str(document_id))

    assert qdrant.eligibility_calls == [(str(document_id), False)]


class _Qdrant:
    def __init__(self) -> None:
        self.eligibility_calls: list[tuple[str, bool]] = []

    async def set_document_eligibility(self, document_id: str, eligible: bool) -> None:
        self.eligibility_calls.append((document_id, eligible))
