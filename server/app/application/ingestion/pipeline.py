from __future__ import annotations

import asyncio
import hashlib
import base64
import io
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from qdrant_client.http.models import PointStruct
from sqlalchemy import select

from app.infrastructure.db.models import Document, Evidence
from app.infrastructure.qdrant.client import QdrantStore
from app.core.logging import enrich_wide_event
from app.core.telemetry import record_degradation


@dataclass(frozen=True)
class ExtractedVisual:
    content: bytes
    page: int
    bounding_box: dict[str, float] | None


@dataclass(frozen=True)
class ExtractedChunk:
    content: str
    context_header: str
    page: int = 1


def _document_title(document: object, path: Path) -> str:
    title = getattr(document, "title", None)
    if title:
        return str(title)
    origin = getattr(document, "origin", None)
    filename = getattr(origin, "filename", None) if origin is not None else None
    return str(filename or path.stem)


def _extract_structured_chunks(markdown: str, title: str) -> list[ExtractedChunk]:
    section_path: list[str] = []
    chunks: list[ExtractedChunk] = []
    for block in re.split(r"\n\s*\n", markdown):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        while lines and lines[0].startswith("#"):
            heading = lines.pop(0)
            level = len(heading) - len(heading.lstrip("#"))
            section_path = section_path[: max(level - 1, 0)]
            section_path.append(heading[level:].strip())
        content = "\n".join(lines).strip()
        if len(content) < 20:
            continue
        section = " > ".join(section_path)
        header = f"Passage from {title}"
        if section:
            header += f", section {section}"
        header += "."
        chunks.extend(
            ExtractedChunk(
                content=content[index : index + 2100],
                context_header=header,
            )
            for index in range(0, len(content), 2100)
        )
    return chunks


def _nearest_text_chunk_index(
    visual_index: int, text_count: int, visual_count: int
) -> int | None:
    if text_count == 0 or visual_count == 0:
        return None
    return min(text_count - 1, visual_index * text_count // visual_count)


def _extract_pdf(
    path,
) -> tuple[list[ExtractedChunk], list[ExtractedVisual], int, list[str]]:
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import (
        DocumentConverter,
        PdfFormatOption,
    )
    from docling.datamodel.pipeline_options import PdfPipelineOptions

    pipeline_options = PdfPipelineOptions(
        generate_page_images=True,
        generate_picture_images=True,
    )
    document = (
        DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        .convert(path)
        .document
    )
    markdown = document.export_to_markdown()
    chunks = _extract_structured_chunks(markdown, _document_title(document, Path(path)))
    page_count = len(getattr(document, "pages", {}) or {})
    visuals: list[ExtractedVisual] = []
    warnings: list[str] = (
        [] if chunks else ["No retrievable text was extracted from this PDF."]
    )
    failed_visuals = 0
    for picture_index, picture in enumerate(getattr(document, "pictures", [])):
        try:
            image = picture.get_image(document)
            stream = io.BytesIO()
            image.save(stream, format="PNG")
            provenance = getattr(picture, "prov", []) or []
            first_provenance = provenance[0] if provenance else None
            page = int(getattr(first_provenance, "page_no", 1) or 1)
            raw_box = getattr(first_provenance, "bbox", None)
            bounding_box = None
            if raw_box is not None:
                bounding_box = {
                    key: float(getattr(raw_box, key))
                    for key in ("l", "t", "r", "b")
                    if getattr(raw_box, key, None) is not None
                }
            visuals.append(
                ExtractedVisual(
                    content=stream.getvalue(),
                    page=page,
                    bounding_box=bounding_box,
                )
            )
        except Exception as exc:
            failed_visuals += 1
            record_degradation(
                "document_visual_extraction",
                picture_index=picture_index,
                error_type=type(exc).__name__,
            )
    if failed_visuals:
        warnings.append("Some visual assets could not be extracted.")
    return chunks, visuals, page_count, warnings


def _canonical_document_query(content_hash: str, source_id: uuid.UUID):
    return select(Document).where(
        Document.content_hash == content_hash,
        Document.source_id != source_id,
        Document.status.in_(("ready", "ready_with_warnings")),
    )


class DocumentIngestionPipeline:
    def __init__(
        self,
        *,
        session_factory,
        redis,
        embedding_client,
        llm_client,
        qdrant_store,
        storage,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._embedding_client = embedding_client
        self._llm_client = llm_client
        self._qdrant_store: QdrantStore = qdrant_store
        self._storage = storage

    async def run(self, document_id: str) -> None:
        identifier = uuid.UUID(document_id)
        started_at = asyncio.get_running_loop().time()
        wide_event: dict[str, object] = {
            "event": "document_ingestion_completed",
            "document_id": str(identifier),
        }
        try:
            async with self._session_factory() as session:
                document = await session.get(Document, identifier)
                if document is None or document.status in {"deleted", "cancelled"}:
                    return
                if document.status in {"ready", "ready_with_warnings"}:
                    await self._qdrant_store.set_document_eligibility(
                        str(document.id), bool(document.is_current)
                    )
                    wide_event["outcome"] = "already_ready"
                    return
                document.status = "processing"
                await session.commit()
            await self._publish(identifier, "parsing", 10)
            async with self._session_factory() as session:
                document = await session.get(Document, identifier)
                if document is None or document.storage_key is None:
                    return
                source_id = document.source_id
                canonical = await session.scalar(
                    _canonical_document_query(document.content_hash, source_id)
                )
                if canonical is not None:
                    wide_event["outcome"] = "deduplicated"
                    previous = await session.scalars(
                        select(Document).where(
                            Document.source_id == document.source_id,
                            Document.id != document.id,
                            Document.is_current.is_(True),
                        )
                    )
                    for version in previous:
                        version.is_current = False
                        await self._qdrant_store.set_document_eligibility(
                            str(version.id), False
                        )
                    document.canonical_document_id = (
                        canonical.canonical_document_id or canonical.id
                    )
                    document.page_count = canonical.page_count
                    document.is_current = True
                    document.status = canonical.status
                    await session.commit()
                    await self._publish(identifier, "deduplicated", 100)
                    await self._publish(identifier, "done", 100)
                    return
                path = self._storage.path(document.storage_key)
            chunks, visuals, page_count, warnings = await asyncio.to_thread(
                _extract_pdf, path
            )
            await self._publish(identifier, "embedding", 45)
            embedding_inputs = [
                f"{chunk.context_header}\n\n{chunk.content}" for chunk in chunks
            ]
            vectors = (
                await self._embedding_client.embed_texts_async(embedding_inputs)
                if embedding_inputs
                else []
            )
            captions = [await self._caption_image(visual.content) for visual in visuals]
            image_vectors: list[list[float]] = []
            if visuals:
                try:
                    image_vectors = await self._embedding_client.embed_images_async(
                        [visual.content for visual in visuals]
                    )
                except Exception as exc:
                    response = getattr(exc, "response", None)
                    status_code = getattr(response, "status_code", None)
                    if status_code != 422:
                        raise
                    record_degradation(
                        "image_embedding",
                        fallback="caption",
                        visual_count=len(visuals),
                        error_type=type(exc).__name__,
                        status_code=status_code,
                    )
                    image_vectors = await self._embedding_client.embed_texts_async(
                        captions
                    )
            evidence_items: list[
                tuple[str, str, int, ExtractedVisual | None, int | None]
            ] = [
                (chunk.content, chunk.context_header, chunk.page, None, None)
                for chunk in chunks
            ]
            evidence_items.extend(
                (
                    caption,
                    f"Image anchor from document, page {visual.page}.",
                    visual.page,
                    visual,
                    _nearest_text_chunk_index(visual_index, len(chunks), len(visuals)),
                )
                for visual_index, (visual, caption) in enumerate(
                    zip(visuals, captions, strict=True)
                )
            )
            vectors.extend(image_vectors)
            async with self._session_factory() as session:
                document = await session.get(Document, identifier)
                if document is None or document.status == "deleted":
                    return
                rows: list[Evidence] = []
                for index, (
                    content,
                    context_header,
                    page,
                    visual,
                    nearest_index,
                ) in enumerate(evidence_items):
                    asset_key = None
                    if visual is not None:
                        asset_key = f"assets/{document.id}/{index}.png"
                        self._storage.write(asset_key, visual.content)
                    row = Evidence(
                        document_id=document.id,
                        locator=f"{document.id}:c{index}",
                        content=content,
                        content_hash=hashlib.sha256(content.encode()).hexdigest(),
                        context_header=context_header,
                        page=page,
                        chunk_index=index,
                        token_count=len(content.split()),
                        extra={
                            "kind": "visual" if visual is not None else "text",
                            "asset_key": asset_key,
                            "nearest_text_locator": (
                                f"{document.id}:c{nearest_index}"
                                if nearest_index is not None
                                else None
                            ),
                            "bounding_box": (
                                visual.bounding_box if visual is not None else None
                            ),
                        },
                    )
                    session.add(row)
                    rows.append(row)
                await session.flush()
                await self._qdrant_store.upsert_points(
                    [
                        PointStruct(
                            id=str(row.id),
                            vector={
                                "dense": vector,
                                "sparse": QdrantStore._text_to_sparse_vector(
                                    f"{row.context_header}\n\n{row.content}"
                                ),
                            },
                            payload={
                                "evidence_id": str(row.id),
                                "document_id": str(document.id),
                                "source_id": str(document.source_id),
                                "eligible": False,
                                "page": row.page,
                                "locator": row.locator,
                                "context_header": row.context_header,
                                "kind": row.extra.get("kind"),
                                "nearest_text_locator": row.extra.get(
                                    "nearest_text_locator"
                                ),
                                "bounding_box": row.extra.get("bounding_box"),
                            },
                        )
                        for row, vector in zip(rows, vectors, strict=True)
                    ]
                )
                previous = await session.scalars(
                    select(Document).where(
                        Document.source_id == document.source_id,
                        Document.id != document.id,
                        Document.is_current.is_(True),
                    )
                )
                for version in previous:
                    version.is_current = False
                    await self._qdrant_store.set_document_eligibility(
                        str(version.id), False
                    )
                document.is_current = True
                document.page_count = page_count
                document.warnings = warnings
                document.status = "ready_with_warnings" if warnings else "ready"
                await session.commit()
                await self._qdrant_store.set_document_eligibility(
                    str(document.id), True
                )
            await self._publish(identifier, "done", 100)
            wide_event["outcome"] = "success"
        except asyncio.CancelledError:
            error_message = (
                "Document ingestion was cancelled or exceeded its worker timeout."
            )
            async with self._session_factory() as session:
                document = await session.get(Document, identifier)
                if document is not None and document.status == "processing":
                    document.status = "failed"
                    document.error_message = error_message
                    await session.commit()
            await self._publish(identifier, "failed", 100, error=error_message)
            raise
        except Exception as exc:
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            async with self._session_factory() as session:
                document = await session.get(Document, identifier)
                if document is not None:
                    document.status = "failed"
                    document.error_message = str(exc)[:2000]
                    await session.commit()
            await self._publish(identifier, "failed", 100, error=str(exc))
            raise
        finally:
            wide_event["duration_ms"] = round(
                (asyncio.get_running_loop().time() - started_at) * 1000, 2
            )
            enrich_wide_event(ingestion=wide_event)

    async def _publish(
        self, document_id: uuid.UUID, stage: str, progress: int, **extra
    ) -> None:
        event = "done" if stage in {"done", "failed"} else "progress"
        await self._redis.publish(
            f"document:{document_id}:events",
            json.dumps(
                {
                    "event": event,
                    "data": {
                        "document_id": str(document_id),
                        "stage": stage,
                        "progress": progress,
                        **extra,
                    },
                }
            ),
        )

    async def _caption_image(self, image: bytes) -> str:
        response = await self._llm_client.generate(
            [
                {
                    "role": "system",
                    "content": "Describe this document visual concisely for retrieval and citation.",
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(image).decode("ascii")
                            },
                        }
                    ],
                },
            ]
        )
        return response.strip() or "Visual from document"
