from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from collections.abc import AsyncIterator

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.schemas.documents import DocumentListResponse, DocumentResponse
from app.api.sse.sse import redis_pubsub_stream, sse_event
from app.core.logging import enrich_wide_event
from app.core.telemetry import inject_job_context
from app.infrastructure.db.models import Document, Source

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/{document_id}/assets/{asset_name}")
async def get_document_asset(document_id: UUID, asset_name: str, request: Request):
    if Path(asset_name).name != asset_name or Path(asset_name).suffix.lower() != ".png":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid asset"
        )
    async with request.app.state.session_factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
    path = request.app.state.document_storage.path(f"assets/{document_id}/{asset_name}")
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    return FileResponse(path, media_type="image/png")


def _response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        document_id=document.id,
        source_id=document.source_id,
        source_key=document.source.source_key,
        title=document.title,
        version_number=document.version_number,
        status=document.status,
        is_current=document.is_current,
        original_filename=document.original_filename,
        page_count=document.page_count,
        byte_size=document.byte_size,
        warnings=list(document.warnings or []),
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request, file: UploadFile = File(...), source_key: str | None = Form(None)
) -> DocumentResponse:
    if request.app.state.job_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Document processing is unavailable"},
        )
    filename = file.filename
    if (
        file.content_type not in {"application/pdf", "application/x-pdf"}
        or not filename
        or not filename.lower().endswith(".pdf")
    ):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF uploads are supported",
        )
    content = await file.read()
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Upload is not a valid PDF"
        )
    if len(content) > request.app.state.settings.ingestion.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload exceeds the 25 MB limit",
        )
    content_hash = hashlib.sha256(content).hexdigest()
    async with request.app.state.session_factory() as session:
        source = None
        if source_key:
            source = await session.scalar(
                select(Source).where(Source.source_key == source_key.strip())
            )
            if source is None or source.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Source not found"
                )
            existing = await session.scalar(
                select(Document)
                .options(selectinload(Document.source))
                .where(
                    Document.source_id == source.id,
                    Document.content_hash == content_hash,
                )
            )
            if existing is not None:
                enrich_wide_event(
                    action="document.upload.duplicate",
                    document={
                        "id": str(existing.id),
                        "source_id": str(existing.source_id),
                        "version": existing.version_number,
                        "status": existing.status,
                        "byte_size": len(content),
                    },
                )
                return _response(existing)
        else:
            source = Source(source_key=str(uuid4()), title=Path(filename).stem)
            session.add(source)
            await session.flush()
        version_number = (
            await session.scalar(
                select(func.coalesce(func.max(Document.version_number), 0) + 1).where(
                    Document.source_id == source.id
                )
            )
        ) or 1
        document_id = uuid4()
        storage_key = request.app.state.document_storage.key_for_original(
            document_id, filename
        )
        request.app.state.document_storage.write(storage_key, content)
        document = Document(
            id=document_id,
            source_id=source.id,
            title=Path(filename).stem,
            slug=f"{source.source_key}-v{version_number}",
            source_path=storage_key,
            storage_key=storage_key,
            source_type="pdf",
            original_filename=filename,
            content_type=file.content_type,
            byte_size=len(content),
            content_hash=content_hash,
            page_count=0,
            version_number=version_number,
            status="queued",
            is_current=False,
        )
        session.add(document)
        await session.commit()
        await session.refresh(document, attribute_names=["source"])
    await request.app.state.job_queue.enqueue_job(
        "run_document_ingestion", str(document.id), inject_job_context()
    )
    enrich_wide_event(
        action="document.upload",
        document={
            "id": str(document.id),
            "source_id": str(document.source_id),
            "version": document.version_number,
            "status": document.status,
            "byte_size": document.byte_size,
            "content_type": document.content_type,
        },
    )
    return _response(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    request: Request,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    async with request.app.state.session_factory() as session:
        total = await session.scalar(select(func.count()).select_from(Document)) or 0
        result = await session.execute(
            select(Document)
            .options(selectinload(Document.source))
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        response = DocumentListResponse(
            items=[_response(document) for document in result.scalars()],
            limit=limit,
            offset=offset,
            total=total,
        )
        enrich_wide_event(
            action="document.list",
            result_count=len(response.items),
            total=total,
            pagination={"limit": limit, "offset": offset},
        )
        return response


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID, request: Request) -> DocumentResponse:
    async with request.app.state.session_factory() as session:
        document = await session.scalar(
            select(Document)
            .options(selectinload(Document.source))
            .where(Document.id == document_id)
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
        enrich_wide_event(
            action="document.get",
            document={
                "id": str(document.id),
                "source_id": str(document.source_id),
                "version": document.version_number,
                "status": document.status,
            },
        )
        return _response(document)


async def _events(request: Request, document_id: UUID) -> AsyncIterator[str]:
    async with request.app.state.session_factory() as session:
        document = await session.scalar(
            select(Document)
            .options(selectinload(Document.source))
            .where(Document.id == document_id)
        )
        if document is None:
            return
        snapshot = _response(document).model_dump(mode="json")
    yield sse_event("snapshot", snapshot)
    if snapshot["status"] in {
        "ready",
        "ready_with_warnings",
        "failed",
        "deleted",
        "cancelled",
    }:
        yield sse_event("done", snapshot)
        return
    async for event in redis_pubsub_stream(
        request.app.state.redis, f"document:{document_id}:events"
    ):
        yield event


@router.get("/{document_id}/events")
async def document_events(document_id: UUID, request: Request) -> StreamingResponse:
    async with request.app.state.session_factory() as session:
        exists = await session.get(Document, document_id)
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
    enrich_wide_event(
        action="document.events",
        document={"id": str(document_id), "status": exists.status},
    )
    return StreamingResponse(
        _events(request, document_id), media_type="text/event-stream"
    )


@router.post("/{document_id}/retries", response_model=DocumentResponse)
async def create_document_retry(
    document_id: UUID, request: Request
) -> DocumentResponse:
    if request.app.state.job_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Document processing is unavailable"},
        )
    async with request.app.state.session_factory() as session:
        document = await session.scalar(
            select(Document)
            .options(selectinload(Document.source))
            .where(Document.id == document_id)
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
        if document.status != "failed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only failed documents can be retried",
            )
        document.status = "queued"
        document.error_message = None
        await session.commit()
        await session.refresh(document, attribute_names=["source"])
    await request.app.state.job_queue.enqueue_job(
        "run_document_ingestion", str(document_id), inject_job_context()
    )
    enrich_wide_event(
        action="document.retry",
        document={
            "id": str(document.id),
            "source_id": str(document.source_id),
            "version": document.version_number,
            "status": document.status,
        },
    )
    return _response(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, request: Request) -> None:
    async with request.app.state.session_factory() as session:
        document = await session.scalar(
            select(Document)
            .options(selectinload(Document.source))
            .where(Document.id == document_id)
        )
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )
        document.source.deleted_at = datetime.now(timezone.utc)
        versions = list(
            await session.scalars(
                select(Document).where(Document.source_id == document.source_id)
            )
        )
        for version in versions:
            version.status = "deleted"
            version.is_current = False
            await request.app.state.qdrant_store.set_document_eligibility(
                str(version.id), False
            )
        await session.commit()
        enrich_wide_event(
            action="document.delete",
            document={
                "id": str(document.id),
                "source_id": str(document.source_id),
                "version_count": len(versions),
                "status": "deleted",
            },
        )
