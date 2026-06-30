from __future__ import annotations

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams

from app.core.config import QdrantSettings


class QdrantStore:
    def __init__(
        self,
        settings: QdrantSettings,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        self._collection = settings.evidence_collection
        self._client = client or AsyncQdrantClient(url=settings.url)

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            await self._client.create_collection(
                self._collection,
                vectors_config=VectorParams(
                    size=768,
                    distance=Distance.COSINE,
                ),
            )

    async def reset_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if exists:
            await self._client.delete_collection(self._collection)
        await self._client.create_collection(
            self._collection,
            vectors_config=VectorParams(
                size=768,
                distance=Distance.COSINE,
            ),
        )

    async def upsert_points(self, points: list) -> None:
        await self._client.upsert(
            self._collection,
            points=points,
            wait=True,
        )
