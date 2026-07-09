from __future__ import annotations

import inspect
import logging
import re
from time import perf_counter

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    Distance,
    Fusion,
    FusionQuery,
    Modifier,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.core.config import QdrantSettings

logger = logging.getLogger(__name__)

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
        self._client = client or AsyncQdrantClient(url=settings.url)

    @staticmethod
    def _vectors_config() -> dict[str, VectorParams]:
        return {
            "dense": VectorParams(
                size=768,
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

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result

    async def hybrid_search(
        self,
        *,
        query_text: str,
        dense_vector: list[float],
        dense_limit: int = 20,
        sparse_limit: int = 20,
        fused_limit: int = 20,
    ) -> list:
        started_at = perf_counter()

        wide_event: dict[str, object] = {
            "event": "hybrid_search",
            "collection": self._collection,
            "dense_limit": dense_limit,
            "sparse_limit": sparse_limit,
            "fused_limit": fused_limit,
        }

        try:
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
            )
            wide_event["result_count"] = len(response.points)
            wide_event["outcome"] = "success"
            return response.points
        except Exception as exc:
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            raise
        finally:
            wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            logger.info("hybrid_search", extra={"wide_event": wide_event})
