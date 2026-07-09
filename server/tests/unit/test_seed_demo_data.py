from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.seed.seed_demo_data import seed_demo_data


class _FakeResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self) -> None:
        self.documents = []
        self.evidence = []
        self.committed = False
        self.rolled_back = False
        self.executed_statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, statement):
        self.executed_statements.append(statement)
        return _FakeResult(None)

    def add(self, item) -> None:
        self.documents.append(item)

    def add_all(self, items) -> None:
        self.evidence.extend(items)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession, bind: object | None = None) -> None:
        self._session = session
        self.kw = {"bind": bind} if bind is not None else {}

    def __call__(self) -> _FakeSession:
        return self._session


class _FakeConnection:
    def __init__(self) -> None:
        self.callbacks: list[object] = []

    async def run_sync(self, callback) -> None:
        self.callbacks.append(callback)


class _FakeBeginContext:
    def __init__(self, connection: _FakeConnection) -> None:
        self._connection = connection

    async def __aenter__(self) -> _FakeConnection:
        return self._connection

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeEngine:
    def __init__(self) -> None:
        self.connection = _FakeConnection()

    def begin(self) -> _FakeBeginContext:
        return _FakeBeginContext(self.connection)


class _FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [
            [float(index), float(index) + 0.1] for index, _ in enumerate(texts, start=1)
        ]


class _FailingEmbeddingClient:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding failed")


class _BadChunkEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if any(text == "bad" for text in texts):
            raise httpx.HTTPStatusError(
                "400 Client Error",
                request=httpx.Request(
                    "POST", "http://optiplex-3020:8081/v1/embeddings"
                ),
                response=httpx.Response(400),
            )
        return [
            [float(index), float(index) + 0.1] for index, _ in enumerate(texts, start=1)
        ]


class _FakeQdrantStore:
    def __init__(self) -> None:
        self.points: list[Any] | None = None
        self.reset_called = False

    async def reset_collection(self) -> None:
        self.reset_called = True

    async def upsert_points(self, points) -> None:
        self.points = points


@pytest.mark.asyncio
async def test_seed_demo_data_loads_demo_document(tmp_path: Path) -> None:
    seed_dir = tmp_path / "demo-corpus"
    seed_dir.mkdir()
    artifact_path = seed_dir / "attention-is-all-you-need.json"
    artifact_path.write_text(
        json.dumps(
            {
                "document": {
                    "title": "Attention Is All You Need",
                    "slug": "attention-is-all-you-need",
                    "source_path": "corpus/attention-is-all-you-need.pdf",
                    "source_type": "pdf",
                    "content_hash": "doc-hash",
                    "page_count": 15,
                    "metadata": {},
                },
                "evidence": [
                    {
                        "locator": "attention-is-all-you-need-p1-c0",
                        "content": "Transformers rely on attention.",
                        "content_hash": "chunk-1",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 0,
                        "token_count": 4,
                        "metadata": {},
                    },
                    {
                        "locator": "attention-is-all-you-need-p2-c1",
                        "content": "The decoder attends to encoder outputs.",
                        "content_hash": "chunk-2",
                        "context_header": "Passage from Attention Is All You Need, page 2.",
                        "page": 2,
                        "chunk_index": 1,
                        "token_count": 6,
                        "metadata": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    session = _FakeSession()
    engine = _FakeEngine()
    session_factory = _FakeSessionFactory(session, bind=engine)
    embedding_client = _FakeEmbeddingClient()
    qdrant_store = _FakeQdrantStore()

    seeded_count = await seed_demo_data(
        session_factory=session_factory,  # type: ignore[reportArgumentType]
        qdrant_store=qdrant_store,  # type: ignore[reportArgumentType]
        embedding_client=embedding_client,  # type: ignore[reportArgumentType]
        seed_dir=seed_dir,
    )

    assert seeded_count == 1
    assert qdrant_store.reset_called is True
    assert len(engine.connection.callbacks) == 2
    assert session.committed is True
    assert session.rolled_back is False
    assert len(session.documents) == 1
    assert len(session.evidence) == 2
    assert qdrant_store.points is not None
    assert len(qdrant_store.points) == 2
    assert embedding_client.calls == [
        [
            "Transformers rely on attention.",
            "The decoder attends to encoder outputs.",
        ]
    ]

    document = session.documents[0]
    assert document.title == "Attention Is All You Need"
    assert document.slug == "attention-is-all-you-need"
    assert document.source_path == "corpus/attention-is-all-you-need.pdf"

    first_evidence = session.evidence[0]
    second_evidence = session.evidence[1]
    assert first_evidence.document_id == document.id
    assert second_evidence.document_id == document.id

    assert len(qdrant_store.points) == 2
    first_point = qdrant_store.points[0]
    assert uuid.UUID(str(first_point.id)) == first_evidence.id
    assert "sparse" in first_point.vector
    assert first_point.vector["dense"] == [1.0, 1.1]
    assert hasattr(first_point.vector["sparse"], "indices")
    assert hasattr(first_point.vector["sparse"], "values")
    assert first_point.payload == {
        "evidence_id": str(first_evidence.id),
        "document_id": str(document.id),
        "document_title": "Attention Is All You Need",
        "document_slug": "attention-is-all-you-need",
        "locator": "attention-is-all-you-need-p1-c0",
        "page": 1,
        "chunk_index": 0,
        "context_header": "Passage from Attention Is All You Need, page 1.",
    }


@pytest.mark.asyncio
async def test_seed_demo_data_rebuilds_sql_schema_before_reseeding(
    tmp_path: Path,
) -> None:
    seed_dir = tmp_path / "demo-corpus"
    seed_dir.mkdir()
    (seed_dir / "attention-is-all-you-need.json").write_text(
        json.dumps(
            {
                "document": {
                    "title": "Attention Is All You Need",
                    "slug": "attention-is-all-you-need",
                    "source_path": "corpus/attention-is-all-you-need.pdf",
                    "source_type": "pdf",
                    "content_hash": "doc-hash",
                    "page_count": 15,
                    "metadata": {},
                },
                "evidence": [
                    {
                        "locator": "attention-is-all-you-need-p1-c0",
                        "content": "Transformers rely on attention.",
                        "content_hash": "chunk-1",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 0,
                        "token_count": 4,
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    session = _FakeSession()
    engine = _FakeEngine()
    session_factory = _FakeSessionFactory(session, bind=engine)
    embedding_client = _FakeEmbeddingClient()
    qdrant_store = _FakeQdrantStore()

    seeded_count = await seed_demo_data(
        session_factory=session_factory,  # type: ignore[reportArgumentType]
        qdrant_store=qdrant_store,  # type: ignore[reportArgumentType]
        embedding_client=embedding_client,  # type: ignore[reportArgumentType]
        seed_dir=seed_dir,
    )

    assert seeded_count == 1
    assert session.executed_statements == []
    assert len(engine.connection.callbacks) == 2
    assert qdrant_store.reset_called is True
    assert len(session.documents) == 1
    assert len(session.evidence) == 1
    assert embedding_client.calls == [["Transformers rely on attention."]]
    assert qdrant_store.points is not None


@pytest.mark.asyncio
async def test_seed_demo_data_rolls_back_when_embedding_fails(tmp_path: Path) -> None:
    seed_dir = tmp_path / "demo-corpus"
    seed_dir.mkdir()
    (seed_dir / "attention-is-all-you-need.json").write_text(
        json.dumps(
            {
                "document": {
                    "title": "Attention Is All You Need",
                    "slug": "attention-is-all-you-need",
                    "source_path": "corpus/attention-is-all-you-need.pdf",
                    "source_type": "pdf",
                    "content_hash": "doc-hash",
                    "page_count": 15,
                    "metadata": {},
                },
                "evidence": [
                    {
                        "locator": "attention-is-all-you-need-p1-c0",
                        "content": "Transformers rely on attention.",
                        "content_hash": "chunk-1",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 0,
                        "token_count": 4,
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    session = _FakeSession()
    engine = _FakeEngine()
    session_factory = _FakeSessionFactory(session, bind=engine)
    qdrant_store = _FakeQdrantStore()

    with pytest.raises(RuntimeError, match="embedding failed"):
        await seed_demo_data(
            session_factory=session_factory,  # type: ignore[reportArgumentType]
            qdrant_store=qdrant_store,  # type: ignore[reportArgumentType]
            embedding_client=_FailingEmbeddingClient(),  # type: ignore[reportArgumentType]
            seed_dir=seed_dir,
        )

    assert session.committed is False
    assert session.rolled_back is True
    assert qdrant_store.points is None
    assert qdrant_store.reset_called is True
    assert session.executed_statements == []
    assert len(engine.connection.callbacks) == 2


@pytest.mark.asyncio
async def test_seed_demo_data_batches_embedding_requests(
    tmp_path: Path, monkeypatch
) -> None:
    seed_dir = tmp_path / "demo-corpus"
    seed_dir.mkdir()
    (seed_dir / "attention-is-all-you-need.json").write_text(
        json.dumps(
            {
                "document": {
                    "title": "Attention Is All You Need",
                    "slug": "attention-is-all-you-need",
                    "source_path": "corpus/attention-is-all-you-need.pdf",
                    "source_type": "pdf",
                    "content_hash": "doc-hash",
                    "page_count": 15,
                    "metadata": {},
                },
                "evidence": [
                    {
                        "locator": "attention-is-all-you-need-p1-c0",
                        "content": "first",
                        "content_hash": "chunk-1",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 0,
                        "token_count": 1,
                        "metadata": {},
                    },
                    {
                        "locator": "attention-is-all-you-need-p1-c1",
                        "content": "second",
                        "content_hash": "chunk-2",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 1,
                        "token_count": 1,
                        "metadata": {},
                    },
                    {
                        "locator": "attention-is-all-you-need-p1-c2",
                        "content": "third",
                        "content_hash": "chunk-3",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 2,
                        "token_count": 1,
                        "metadata": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.seed.seed_demo_data.EMBEDDING_BATCH_SIZE", 2)

    session = _FakeSession()
    engine = _FakeEngine()
    session_factory = _FakeSessionFactory(session, bind=engine)
    embedding_client = _FakeEmbeddingClient()
    qdrant_store = _FakeQdrantStore()

    seeded_count = await seed_demo_data(
        session_factory=session_factory,  # type: ignore[reportArgumentType]
        qdrant_store=qdrant_store,  # type: ignore[reportArgumentType]
        embedding_client=embedding_client,  # type: ignore[reportArgumentType]
        seed_dir=seed_dir,
    )

    assert seeded_count == 1
    assert embedding_client.calls == [["first", "second"], ["third"]]
    assert qdrant_store.points is not None
    assert len(qdrant_store.points) == 3
    for point in qdrant_store.points:
        assert "dense" in point.vector
        assert "sparse" in point.vector
        assert hasattr(point.vector["sparse"], "indices")
        assert hasattr(point.vector["sparse"], "values")
    assert [point.vector["dense"] for point in qdrant_store.points] == [
        [1.0, 1.1],
        [2.0, 2.1],
        [1.0, 1.1],
    ]


@pytest.mark.asyncio
async def test_seed_demo_data_skips_bad_evidence_chunk_on_400(
    tmp_path: Path, monkeypatch
) -> None:
    seed_dir = tmp_path / "demo-corpus"
    seed_dir.mkdir()
    (seed_dir / "attention-is-all-you-need.json").write_text(
        json.dumps(
            {
                "document": {
                    "title": "Attention Is All You Need",
                    "slug": "attention-is-all-you-need",
                    "source_path": "corpus/attention-is-all-you-need.pdf",
                    "source_type": "pdf",
                    "content_hash": "doc-hash",
                    "page_count": 15,
                    "metadata": {},
                },
                "evidence": [
                    {
                        "locator": "attention-is-all-you-need-p1-c0",
                        "content": "good-1",
                        "content_hash": "chunk-1",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 0,
                        "token_count": 1,
                        "metadata": {},
                    },
                    {
                        "locator": "attention-is-all-you-need-p1-c1",
                        "content": "bad",
                        "content_hash": "chunk-2",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 1,
                        "token_count": 1,
                        "metadata": {},
                    },
                    {
                        "locator": "attention-is-all-you-need-p1-c2",
                        "content": "good-2",
                        "content_hash": "chunk-3",
                        "context_header": "Passage from Attention Is All You Need, page 1.",
                        "page": 1,
                        "chunk_index": 2,
                        "token_count": 1,
                        "metadata": {},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("app.seed.seed_demo_data.EMBEDDING_BATCH_SIZE", 3)

    session = _FakeSession()
    engine = _FakeEngine()
    session_factory = _FakeSessionFactory(session, bind=engine)
    embedding_client = _BadChunkEmbeddingClient()
    qdrant_store = _FakeQdrantStore()

    seeded_count = await seed_demo_data(
        session_factory=session_factory,  # type: ignore[reportArgumentType]
        qdrant_store=qdrant_store,  # type: ignore[reportArgumentType]
        embedding_client=embedding_client,  # type: ignore[reportArgumentType]
        seed_dir=seed_dir,
    )

    assert seeded_count == 1
    assert embedding_client.calls == [
        ["good-1", "bad", "good-2"],
        ["good-1"],
        ["bad", "good-2"],
        ["bad"],
        ["good-2"],
    ]
    assert [row.locator for row in session.evidence] == [
        "attention-is-all-you-need-p1-c0",
        "attention-is-all-you-need-p1-c2",
    ]
    assert qdrant_store.points is not None
    assert len(qdrant_store.points) == 2
