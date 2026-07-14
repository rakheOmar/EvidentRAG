from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.ingestion.pipeline import (
    DocumentIngestionPipeline,
    _extract_docling_chunks,
    _nearest_text_chunk_index,
    _processing_lease_active,
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

    async def scalars(self, statement):
        return [self.document]

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


def test_docling_chunks_preserve_page_and_section_provenance(monkeypatch) -> None:
    chunk = SimpleNamespace(
        text="Users may request access through the portal.",
        meta=SimpleNamespace(
            headings=["Handbook", "Access"],
            origin=SimpleNamespace(page_no=7),
            doc_items=[],
        ),
    )
    monkeypatch.setattr(
        "app.application.ingestion.pipeline._create_chunker",
        lambda: SimpleNamespace(chunk=lambda _document: [chunk]),
    )

    chunks = _extract_docling_chunks(object(), "Security Guide")

    assert len(chunks) == 1
    assert chunks[0].content == "Users may request access through the portal."
    assert chunks[0].page == 7
    assert chunks[0].context_header == (
        "Passage from Security Guide, section Handbook > Access, page 7."
    )


def test_processing_lease_distinguishes_active_and_abandoned_jobs() -> None:
    now = datetime.now(timezone.utc)

    assert _processing_lease_active(
        SimpleNamespace(updated_at=now - timedelta(seconds=30)), 60
    )
    assert not _processing_lease_active(
        SimpleNamespace(updated_at=now - timedelta(seconds=90)), 60
    )


@pytest.mark.parametrize(
    ("visual_index", "text_count", "visual_count", "expected_index"),
    [
        (0, 4, 2, 0),
        (1, 4, 2, 2),
        (0, 0, 2, None),
    ],
    ids=["first-visual", "last-visual", "no-text-chunks"],
)
def test_visuals_are_associated_with_nearest_text_chunk_by_source_order(
    visual_index: int,
    text_count: int,
    visual_count: int,
    expected_index: int | None,
) -> None:
    assert (
        _nearest_text_chunk_index(visual_index, text_count, visual_count)
        == expected_index
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_current", "expected_eligibility"),
    [(True, True), (False, False)],
    ids=["current-document", "historical-document"],
)
async def test_ready_ingestion_updates_qdrant_eligibility_without_reingesting(
    is_current: bool,
    expected_eligibility: bool,
) -> None:
    document_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        source_id=uuid4(),
        status="ready",
        is_current=is_current,
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

    assert qdrant.eligibility_calls == [(str(document_id), expected_eligibility)]


class _Qdrant:
    def __init__(self) -> None:
        self.eligibility_calls: list[tuple[str, bool]] = []

    async def set_document_eligibility(self, document_id: str, eligible: bool) -> None:
        self.eligibility_calls.append((document_id, eligible))
