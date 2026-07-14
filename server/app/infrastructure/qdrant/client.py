from __future__ import annotations

import inspect
import re

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    Modifier,
    MatchValue,
    PayloadSchemaType,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.core.config import QdrantSettings
from app.core.telemetry import record_degradation, traced_operation

_FNV_OFFSET_BASIS_32 = 0x811C9DC5
_FNV_PRIME_32 = 0x01000193


def _fnv1a_32(text: str) -> int:
    h = _FNV_OFFSET_BASIS_32
    for byte in text.encode("utf-8"):
        h = ((h ^ byte) * _FNV_PRIME_32) & 0xFFFFFFFF
    return h


class QdrantStore:
    def __init__(
        self,
        settings: QdrantSettings,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._collection = settings.evidence_collection
        self._vector_dimensions = settings.vector_dimensions
        self._client = client or AsyncQdrantClient(url=settings.url)

    def _vectors_config(self) -> dict[str, VectorParams]:
        return {
            "dense": VectorParams(
                size=self._vector_dimensions,
                distance=Distance.COSINE,
            )
        }

    @staticmethod
    def _sparse_vectors_config() -> dict[str, SparseVectorParams]:
        return {"sparse": SparseVectorParams(modifier=Modifier.IDF)}

    @staticmethod
    def _text_to_sparse_vector(text: str) -> SparseVector:
        tokens = re.findall(r"[a-z]+", text.lower())
        tokens = [t for t in tokens if len(t) > 1]
        freq: dict[int, float] = {}
        for token in tokens:
            idx = _fnv1a_32(token)
            freq[idx] = freq.get(idx, 0.0) + 1.0
        return SparseVector(
            indices=list(freq.keys()),
            values=list(freq.values()),
        )

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            await self._client.create_collection(
                self._collection,
                vectors_config=self._vectors_config(),
                sparse_vectors_config=self._sparse_vectors_config(),
            )
        else:
            collection = await self._client.get_collection(self._collection)
            vectors = collection.config.params.vectors
            dense = vectors.get("dense") if isinstance(vectors, dict) else vectors
            actual_dimensions = getattr(dense, "size", None)
            if actual_dimensions != self._vector_dimensions:
                raise RuntimeError(
                    f"Qdrant collection {self._collection!r} uses "
                    f"{actual_dimensions} dense dimensions, but configuration requires "
                    f"{self._vector_dimensions}. Reindex the collection before startup."
                )
        for field_name, schema in (
            ("eligible", PayloadSchemaType.BOOL),
            ("document_id", PayloadSchemaType.KEYWORD),
            ("source_id", PayloadSchemaType.KEYWORD),
        ):
            try:
                await self._client.create_payload_index(
                    self._collection, field_name=field_name, field_schema=schema
                )
            except Exception:
                record_degradation(
                    "qdrant_payload_index",
                    field=field_name,
                )

    async def reset_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if exists:
            await self._client.delete_collection(self._collection)
        await self._client.create_collection(
            self._collection,
            vectors_config=self._vectors_config(),
            sparse_vectors_config=self._sparse_vectors_config(),
        )

    async def upsert_points(self, points: list) -> None:
        await self._client.upsert(
            self._collection,
            points=points,
            wait=True,
        )

    async def set_document_eligibility(self, document_id: str, eligible: bool) -> None:
        await self._client.set_payload(
            self._collection,
            payload={"eligible": eligible},
            points=Filter(
                must=[
                    FieldCondition(
                        key="document_id", match=MatchValue(value=document_id)
                    )
                ]
            ),
            wait=True,
        )

    async def delete_document_points(self, document_id: str) -> None:
        await self._client.delete(
            self._collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id", match=MatchValue(value=document_id)
                    )
                ]
            ),
            wait=True,
        )

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    async def health_check(self) -> None:
        await self._client.get_collection(self._collection)

    async def hybrid_search(
        self,
        *,
        query_text: str,
        dense_vector: list[float],
        dense_limit: int = 20,
        sparse_limit: int = 20,
        fused_limit: int = 20,
    ) -> list:
        operation_context = {
            "collection": self._collection,
            "dense_limit": dense_limit,
            "sparse_limit": sparse_limit,
            "fused_limit": fused_limit,
        }

        with traced_operation("qdrant.hybrid_search", **operation_context) as operation:
            response = await self._client.query_points(
                self._collection,
                prefetch=[
                    Prefetch(query=dense_vector, using="dense", limit=dense_limit),
                    Prefetch(
                        query=self._text_to_sparse_vector(query_text),
                        using="sparse",
                        limit=sparse_limit,
                    ),
                ],
                query=FusionQuery(fusion=Fusion.RRF),
                limit=fused_limit,
                with_payload=True,
                query_filter=Filter(
                    must=[FieldCondition(key="eligible", match=MatchValue(value=True))]
                ),
            )
            operation["result_count"] = len(response.points)
            return response.points
