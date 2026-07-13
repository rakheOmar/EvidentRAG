from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.infrastructure.db.models import Document, Source


class _JobQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    async def enqueue_job(
        self,
        function_name: str,
        document_id: str,
        trace_context: dict[str, str],
    ) -> None:
        self.calls.append((function_name, document_id, trace_context))


class _DocumentStorage:
    def __init__(self) -> None:
        self.writes: dict[str, bytes] = {}

    def key_for_original(self, document_id: UUID, filename: str) -> str:
        return f"originals/{document_id}.pdf"

    def write(self, key: str, content: bytes) -> None:
        self.writes[key] = content


class _QdrantStore:
    def __init__(self) -> None:
        self.eligibility_calls: list[tuple[str, bool]] = []

    async def set_document_eligibility(self, document_id: str, eligible: bool) -> None:
        self.eligibility_calls.append((document_id, eligible))


def _configure_document_dependencies(
    client,
) -> tuple[_JobQueue, _DocumentStorage, _QdrantStore]:
    queue = _JobQueue()
    storage = _DocumentStorage()
    qdrant_store = _QdrantStore()
    client.app.state.job_queue = queue
    client.app.state.document_storage = storage
    client.app.state.qdrant_store = qdrant_store
    return queue, storage, qdrant_store


def _upload(client) -> dict[str, object]:
    response = client.post(
        "/api/v1/documents",
        files={"file": ("handbook.pdf", b"%PDF-1.7\ncontent", "application/pdf")},
    )

    assert response.status_code == 201
    return response.json()


def _set_document_status(client, document_id: str, status: str) -> None:
    session_factory = client.app.state.session_factory

    async def _persist() -> None:
        async with session_factory() as session:
            document = await session.get(Document, UUID(document_id))
            assert document is not None
            document.status = status
            document.is_current = status == "ready"
            await session.commit()

    client.portal.call(_persist)


def test_document_upload_validates_pdf_inputs(client) -> None:
    _configure_document_dependencies(client)

    unsupported = client.post(
        "/api/v1/documents",
        files={"file": ("notes.txt", b"text", "text/plain")},
    )
    invalid = client.post(
        "/api/v1/documents",
        files={"file": ("notes.pdf", b"not a pdf", "application/pdf")},
    )
    missing = client.post("/api/v1/documents")

    assert unsupported.status_code == 415
    assert unsupported.json()["error"]["code"] == "unsupported_media_type"
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "bad_request"
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "validation_error"


def test_document_upload_list_detail_and_terminal_events(client) -> None:
    queue, storage, _ = _configure_document_dependencies(client)
    uploaded = _upload(client)
    document_id = uploaded["document_id"]
    assert isinstance(document_id, str)

    assert uploaded["id"] == document_id
    assert uploaded["status"] == "queued"
    function_name, queued_document_id, trace_context = queue.calls[0]
    assert function_name == "run_document_ingestion"
    assert queued_document_id == document_id
    UUID(trace_context["x-request-id"])
    assert list(storage.writes.values()) == [b"%PDF-1.7\ncontent"]

    listing = client.get("/api/v1/documents")
    detail = client.get(f"/api/v1/documents/{document_id}")

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["document_id"] == document_id
    assert detail.status_code == 200
    assert detail.json()["id"] == document_id

    _set_document_status(client, document_id, "ready")

    with client.stream("GET", f"/api/v1/documents/{document_id}/events") as response:
        body = b"".join(response.iter_bytes()).decode("utf-8")

    assert response.status_code == 200
    assert "event: snapshot" in body
    assert "event: done" in body


def test_document_retry_and_delete_tombstones_source(client) -> None:
    queue, _, qdrant_store = _configure_document_dependencies(client)
    uploaded = _upload(client)
    document_id = uploaded["document_id"]
    assert isinstance(document_id, str)
    _set_document_status(client, document_id, "failed")

    retry = client.post(f"/api/v1/documents/{document_id}/retries")

    assert retry.status_code == 200
    assert retry.json()["status"] == "queued"
    function_name, queued_document_id, trace_context = queue.calls[-1]
    assert function_name == "run_document_ingestion"
    assert queued_document_id == document_id
    assert trace_context["x-request-id"] == retry.headers["x-request-id"]

    deleted = client.delete(f"/api/v1/documents/{document_id}")
    missing = client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000000")

    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert qdrant_store.eligibility_calls == [(document_id, False)]

    session_factory = client.app.state.session_factory

    async def _assert_tombstone() -> None:
        async with session_factory() as session:
            document = await session.get(Document, UUID(document_id))
            assert document is not None
            source = await session.scalar(
                select(Source).where(Source.id == document.source_id)
            )
            assert document.status == "deleted"
            assert document.is_current is False
            assert source is not None
            assert source.deleted_at is not None

    client.portal.call(_assert_tombstone)
