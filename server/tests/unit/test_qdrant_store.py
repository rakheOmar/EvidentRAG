from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.config import QdrantSettings
from app.infrastructure.qdrant.client import QdrantStore


@pytest.fixture
def settings() -> QdrantSettings:
    return QdrantSettings(
        url="http://qdrant:6333",
        evidence_collection="evidentrag_evidence",
    )


async def test_ensure_collection_creates_collection_when_missing(
    settings: QdrantSettings,
) -> None:
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = False

    store = QdrantStore(settings=settings, client=mock_client)
    await store.ensure_collection()

    mock_client.collection_exists.assert_awaited_once_with("evidentrag_evidence")
    mock_client.create_collection.assert_awaited_once()
    args, _ = mock_client.create_collection.call_args
    assert args[0] == "evidentrag_evidence"


async def test_ensure_collection_skips_when_exists(settings: QdrantSettings) -> None:
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    store = QdrantStore(settings=settings, client=mock_client)
    await store.ensure_collection()

    mock_client.create_collection.assert_not_called()


async def test_upsert_points_calls_client_with_collection_and_points(
    settings: QdrantSettings,
) -> None:
    mock_client = AsyncMock()

    store = QdrantStore(settings=settings, client=mock_client)
    await store.upsert_points([])

    mock_client.upsert.assert_awaited_once_with(
        "evidentrag_evidence", points=[], wait=True
    )


async def test_reset_collection_recreates_existing_collection(
    settings: QdrantSettings,
) -> None:
    mock_client = AsyncMock()
    mock_client.collection_exists.return_value = True

    store = QdrantStore(settings=settings, client=mock_client)
    await store.reset_collection()

    mock_client.collection_exists.assert_awaited_once_with("evidentrag_evidence")
    mock_client.delete_collection.assert_awaited_once_with("evidentrag_evidence")
    mock_client.create_collection.assert_awaited_once()
