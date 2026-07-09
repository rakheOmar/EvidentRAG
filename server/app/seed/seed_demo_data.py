from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Sequence
from pathlib import Path
from time import perf_counter

import httpx
from qdrant_client.http.models import PointStruct
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.infrastructure.db.models import Base, Document, Evidence
from app.infrastructure.embeddings.embedding import EmbeddingClient
from app.infrastructure.qdrant.client import QdrantStore


DEFAULT_SEED_DIR = Path(__file__).with_name("demo-corpus")
EMBEDDING_BATCH_SIZE = 16
logger = logging.getLogger(__name__)


async def _embed_batch(
    embedding_client: EmbeddingClient,
    texts: Sequence[str],
    locators: Sequence[str],
) -> tuple[list[list[float]], list[int]]:
    try:
        vectors = await asyncio.to_thread(embedding_client.embed_texts, list(texts))
        return vectors, []
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 400:
            raise
        if len(texts) == 1:
            logger.info(
                "seed_embedding_skipped",
                extra={
                    "wide_event": {
                        "event": "seed_embedding_skipped",
                        "locator": locators[0],
                        "outcome": "skipped",
                    }
                },
            )
            return [], [0]

        midpoint = len(texts) // 2
        left_vectors, left_skipped = await _embed_batch(
            embedding_client,
            texts[:midpoint],
            locators[:midpoint],
        )
        right_vectors, right_skipped = await _embed_batch(
            embedding_client,
            texts[midpoint:],
            locators[midpoint:],
        )
        return left_vectors + right_vectors, left_skipped + [
            midpoint + index for index in right_skipped
        ]


async def _embed_evidence_rows(
    embedding_client: EmbeddingClient,
    evidence_rows: Sequence[Evidence],
) -> tuple[list[Evidence], list[list[float]]]:
    kept_rows: list[Evidence] = []
    vectors: list[list[float]] = []

    for start in range(0, len(evidence_rows), EMBEDDING_BATCH_SIZE):
        batch_rows = list(evidence_rows[start : start + EMBEDDING_BATCH_SIZE])
        batch_vectors, skipped_indexes = await _embed_batch(
            embedding_client,
            [row.content for row in batch_rows],
            [row.locator for row in batch_rows],
        )
        skipped_set = set(skipped_indexes)
        kept_rows.extend(
            row for index, row in enumerate(batch_rows) if index not in skipped_set
        )
        vectors.extend(batch_vectors)

    return kept_rows, vectors


async def _recreate_schema(session_factory: async_sessionmaker) -> None:
    bind = getattr(session_factory, "kw", {}).get("bind")
    if bind is None:
        return

    async with bind.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def seed_demo_data(
    session_factory: async_sessionmaker,
    qdrant_store: QdrantStore,
    embedding_client: EmbeddingClient,
    seed_dir: Path = DEFAULT_SEED_DIR,
) -> int:
    started_at = perf_counter()
    seeded_count = 0
    skipped_count = 0
    artifact_paths = sorted(seed_dir.glob("*.json"))
    wide_event: dict[str, object] = {
        "event": "seed_demo_data",
        "seed_dir": str(seed_dir),
        "document_count": len(artifact_paths),
    }

    try:
        await _recreate_schema(session_factory)
        wide_event["schema_recreated"] = True

        await qdrant_store.reset_collection()
        wide_event["qdrant_collection_reset"] = True

        for artifact_path in artifact_paths:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            document_data = payload["document"]
            evidence_data = payload["evidence"]

            async with session_factory() as session:
                try:
                    document_id = uuid.uuid4()
                    document = Document(
                        id=document_id,
                        title=document_data["title"],
                        slug=document_data["slug"],
                        source_path=document_data["source_path"],
                        source_type=document_data["source_type"],
                        content_hash=document_data["content_hash"],
                        page_count=document_data["page_count"],
                        extra=document_data["metadata"],
                    )
                    session.add(document)

                    evidence_rows = []
                    for item in evidence_data:
                        evidence = Evidence(
                            id=uuid.uuid4(),
                            document_id=document_id,
                            locator=item["locator"],
                            content=item["content"],
                            content_hash=item["content_hash"],
                            context_header=item["context_header"],
                            page=item["page"],
                            chunk_index=item["chunk_index"],
                            token_count=item["token_count"],
                            extra=item["metadata"],
                        )
                        evidence_rows.append(evidence)

                    embedded_rows, vectors = await _embed_evidence_rows(
                        embedding_client, evidence_rows
                    )
                    if not embedded_rows:
                        skipped_count += 1
                        logger.info(
                            "seed_document_skipped",
                            extra={
                                "wide_event": {
                                    "event": "seed_document_skipped",
                                    "reason": "no_embeddable_evidence",
                                    "slug": document.slug,
                                    "outcome": "skipped",
                                }
                            },
                        )
                        await session.rollback()
                        continue

                    session.add_all(embedded_rows)
                    await session.flush()
                    points = [
                        PointStruct(
                            id=str(evidence.id),
                            vector={
                                "dense": vector,
                                "sparse": QdrantStore._text_to_sparse_vector(
                                    evidence.content
                                ),
                            },
                            payload={
                                "evidence_id": str(evidence.id),
                                "document_id": str(document.id),
                                "document_title": document.title,
                                "document_slug": document.slug,
                                "locator": evidence.locator,
                                "page": evidence.page,
                                "chunk_index": evidence.chunk_index,
                                "context_header": evidence.context_header,
                            },
                        )
                        for evidence, vector in zip(embedded_rows, vectors, strict=True)
                    ]
                    await qdrant_store.upsert_points(points)
                    await session.commit()
                    seeded_count += 1
                except Exception:
                    await session.rollback()
                    raise

        wide_event["seeded_count"] = seeded_count
        wide_event["skipped_count"] = skipped_count
        wide_event["outcome"] = "success"
        return seeded_count
    except Exception as exc:
        wide_event["seeded_count"] = seeded_count
        wide_event["skipped_count"] = skipped_count
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        logger.info("seed_demo_data", extra={"wide_event": wide_event})
