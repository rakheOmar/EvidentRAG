from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from qdrant_client.http.models import Fusion, FusionQuery, Modifier, SparseVector

from app.core.config import QdrantSettings
from app.infrastructure.qdrant.client import QdrantStore


class TestTextToSparseVector:
    def test_returns_sparse_vector_with_matching_indices_and_values(
        self,
    ) -> None:
        result = QdrantStore._text_to_sparse_vector("hello")

        assert isinstance(result, SparseVector)
        assert len(result.indices) == len(result.values)
        assert len(result.indices) == 1
        assert result.values[0] == 1.0

    def test_empty_text_returns_empty_vectors(self) -> None:
        result = QdrantStore._text_to_sparse_vector("")

        assert isinstance(result, SparseVector)
        assert result.indices == []
        assert result.values == []

    def test_repeated_token_increases_value(self) -> None:
        single = QdrantStore._text_to_sparse_vector("hello")
        repeated = QdrantStore._text_to_sparse_vector("hello hello hello")

        assert single.indices == repeated.indices
        assert repeated.values[0] == 3.0

    def test_multiple_tokens_produce_separate_indices(self) -> None:
        result = QdrantStore._text_to_sparse_vector("cat sat hat")

        assert len(result.indices) == 3
        assert all(v == 1.0 for v in result.values)

    def test_case_insensitive_tokens_map_to_same_index(self) -> None:
        upper = QdrantStore._text_to_sparse_vector("Hello")
        lower = QdrantStore._text_to_sparse_vector("hello")

        assert upper.indices == lower.indices

    def test_short_tokens_are_filtered(self) -> None:
        result = QdrantStore._text_to_sparse_vector("a RAG x")

        assert len(result.indices) == 1

    def test_deterministic_output(self) -> None:
        first = QdrantStore._text_to_sparse_vector("the cat sat on the mat")
        second = QdrantStore._text_to_sparse_vector("the cat sat on the mat")

        assert first.indices == second.indices
        assert first.values == second.values


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
    args, kwargs = mock_client.create_collection.call_args
    assert args[0] == "evidentrag_evidence"
    assert set(kwargs["vectors_config"].keys()) == {"dense"}
    assert kwargs["vectors_config"]["dense"].size == 768
    assert kwargs["sparse_vectors_config"]["sparse"].modifier == Modifier.IDF


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


async def test_hybrid_search_queries_qdrant_with_dense_sparse_and_rrf(
    settings: QdrantSettings,
) -> None:
    mock_client = AsyncMock()
    mock_response = type("Response", (), {"points": ["p1", "p2"]})()
    mock_client.query_points.return_value = mock_response

    store = QdrantStore(settings=settings, client=mock_client)
    result = await store.hybrid_search(
        query_text="what does EvidentRAG say about citations?",
        dense_vector=[0.1, 0.2],
        dense_limit=20,
        sparse_limit=20,
        fused_limit=20,
    )

    assert result == ["p1", "p2"]
    mock_client.query_points.assert_awaited_once()
    args, kwargs = mock_client.query_points.call_args
    assert args[0] == "evidentrag_evidence"
    assert isinstance(kwargs["query"], FusionQuery)
    assert kwargs["query"].fusion == Fusion.RRF
    assert kwargs["limit"] == 20
    assert kwargs["with_payload"] is True

    prefetch = kwargs["prefetch"]
    assert len(prefetch) == 2
    assert prefetch[0].using == "dense"
    assert prefetch[0].query == [0.1, 0.2]
    assert prefetch[0].limit == 20
    assert prefetch[1].using == "sparse"
    assert isinstance(prefetch[1].query, SparseVector)
    expected_sparse = QdrantStore._text_to_sparse_vector(
        "what does EvidentRAG say about citations?"
    )
    assert prefetch[1].query.indices == expected_sparse.indices
    assert prefetch[1].query.values == expected_sparse.values
    assert prefetch[1].limit == 20
