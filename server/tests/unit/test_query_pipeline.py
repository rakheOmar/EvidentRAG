from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from collections.abc import Mapping
from types import SimpleNamespace

import pytest

from app.infrastructure.db.models import Query
from app.infrastructure.reranker.reranker import RerankResult


class _FakeSession:
    def __init__(
        self,
        query: Query,
        evidence_by_id: Mapping[uuid.UUID, object] | None = None,
    ) -> None:
        self._query = query
        self._evidence_by_id = dict(evidence_by_id or {})
        self.committed_statuses: list[str] = []
        self.added_objects: list[object] = []

    async def get(self, model, query_id):
        if model is Query and query_id == self._query.id:
            return self._query
        if query_id in self._evidence_by_id:
            return self._evidence_by_id[query_id]
        return None

    async def commit(self) -> None:
        self.committed_statuses.append(self._query.status)

    def add(self, obj: object) -> None:
        self.added_objects.append(obj)


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionContext:
        return _FakeSessionContext(self._session)


class _FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))


class _FakeEmbeddingClient:
    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return self._vectors


class _FakeQdrantStore:
    def __init__(self, response) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    async def hybrid_search(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class _FakeRerankClient:
    def __init__(self, results: list[RerankResult]) -> None:
        self._results = results
        self.calls: list[dict[str, object]] = []

    async def rerank(
        self, query: str, documents: list[str], top_n: int = 5
    ) -> list[RerankResult]:
        self.calls.append({"query": query, "documents": documents, "top_n": top_n})
        return self._results


class _FakeLLMClient:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks
        self.calls: list[dict[str, object]] = []

    async def generate_stream(self, messages: list[dict[str, str]], model=None):
        self.calls.append({"messages": messages, "model": model})
        for chunk in self._chunks:
            yield chunk


def _make_query() -> Query:
    query = Query(query_text="What does EvidentRAG say about citations?")
    query.id = uuid.uuid4()
    query.created_at = datetime.now(timezone.utc)
    query.updated_at = query.created_at
    return query


@pytest.mark.asyncio
async def test_query_pipeline_run_marks_running_then_completed_and_publishes_events() -> (
    None
):
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    query = _make_query()
    session = _FakeSession(query)
    redis = _FakeRedis()

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
    )

    await pipeline.run(query.id)

    assert session.committed_statuses == ["running", "completed"]
    assert query.status == "completed"
    assert query.completed_at is not None

    channel = f"query:{query.id}:events"
    assert [published_channel for published_channel, _ in redis.published] == [
        channel,
        channel,
    ]

    first_event = json.loads(redis.published[0][1])
    second_event = json.loads(redis.published[1][1])

    assert first_event == {"event": "route_selected", "data": {"route": "simple"}}
    assert second_event == {"event": "done", "data": {"status": "completed"}}


@pytest.mark.asyncio
async def test_query_pipeline_run_embeds_retrieves_and_stages_candidate_traces() -> (
    None
):
    from app.application.query_pipeline.query_pipeline import QueryPipeline
    from app.infrastructure.db.models import QueryEvidenceCandidate

    dense_id = uuid.uuid4()
    sparse_id = uuid.uuid4()
    fused_id = uuid.uuid4()

    class _Point:
        def __init__(self, evidence_id: uuid.UUID, score: float) -> None:
            self.payload = {"evidence_id": str(evidence_id)}
            self.score = score

    query = _make_query()
    session = _FakeSession(query)
    redis = _FakeRedis()
    embedding_client = _FakeEmbeddingClient([[0.1, 0.2]])
    qdrant_store = _FakeQdrantStore(
        {
            "dense": [_Point(dense_id, 0.91)],
            "sparse": [_Point(sparse_id, 0.73)],
            "fused": [_Point(fused_id, 0.88)],
        }
    )

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
        embedding_client=embedding_client,
        qdrant_store=qdrant_store,
    )

    await pipeline.run(query.id)

    assert embedding_client.calls == [[query.query_text]]
    assert qdrant_store.calls == [
        {
            "query_text": query.query_text,
            "dense_vector": [0.1, 0.2],
            "dense_limit": 20,
            "sparse_limit": 20,
            "fused_limit": 20,
        }
    ]

    candidates = [
        obj for obj in session.added_objects if isinstance(obj, QueryEvidenceCandidate)
    ]
    assert [
        (candidate.stage, candidate.evidence_id, candidate.rank, candidate.score)
        for candidate in candidates
    ] == [
        ("dense", dense_id, 0, 0.91),
        ("sparse", sparse_id, 0, 0.73),
        ("fused", fused_id, 0, 0.88),
    ]

    events = [json.loads(message) for _, message in redis.published]
    assert events == [
        {"event": "route_selected", "data": {"route": "simple"}},
        {"event": "retrieving", "data": {"status": "retrieving"}},
        {"event": "done", "data": {"status": "completed"}},
    ]


@pytest.mark.asyncio
async def test_query_pipeline_run_reranks_fused_hits_and_stages_selected_candidates() -> (
    None
):
    from app.application.query_pipeline.query_pipeline import QueryPipeline
    from app.infrastructure.db.models import QueryEvidenceCandidate

    first_id = uuid.uuid4()
    second_id = uuid.uuid4()

    class _Point:
        def __init__(self, evidence_id: uuid.UUID, score: float) -> None:
            self.payload = {"evidence_id": str(evidence_id)}
            self.score = score

    query = _make_query()
    evidence_by_id = {
        first_id: SimpleNamespace(content="first evidence chunk"),
        second_id: SimpleNamespace(content="second evidence chunk"),
    }
    session = _FakeSession(query, evidence_by_id=evidence_by_id)
    redis = _FakeRedis()
    embedding_client = _FakeEmbeddingClient([[0.1, 0.2]])
    qdrant_store = _FakeQdrantStore(
        {
            "dense": [],
            "sparse": [],
            "fused": [_Point(first_id, 0.61), _Point(second_id, 0.58)],
        }
    )
    rerank_client = _FakeRerankClient(
        [
            RerankResult(index=1, relevance_score=0.95),
            RerankResult(index=0, relevance_score=0.72),
        ]
    )

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
        embedding_client=embedding_client,
        qdrant_store=qdrant_store,
        rerank_client=rerank_client,
    )

    await pipeline.run(query.id)

    assert rerank_client.calls == [
        {
            "query": query.query_text,
            "documents": ["first evidence chunk", "second evidence chunk"],
            "top_n": 5,
        }
    ]

    candidates = [
        obj for obj in session.added_objects if isinstance(obj, QueryEvidenceCandidate)
    ]
    reranked = [candidate for candidate in candidates if candidate.stage == "reranked"]
    selected = [candidate for candidate in candidates if candidate.stage == "selected"]

    assert [
        (candidate.evidence_id, candidate.rank, candidate.score)
        for candidate in reranked
    ] == [
        (second_id, 0, 0.95),
        (first_id, 1, 0.72),
    ]
    assert [
        (candidate.evidence_id, candidate.rank, candidate.score)
        for candidate in selected
    ] == [
        (second_id, 0, 0.95),
        (first_id, 1, 0.72),
    ]


@pytest.mark.asyncio
async def test_query_pipeline_run_marks_failed_and_publishes_error_on_exception() -> (
    None
):
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    query = _make_query()
    session = _FakeSession(query)
    redis = _FakeRedis()

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
    )

    async def fail_after_route_selected(session, query: Query, wide_event=None) -> None:
        raise RuntimeError("generation failed")

    pipeline._run_simple_route = fail_after_route_selected  # type: ignore[attr-defined]

    with pytest.raises(RuntimeError, match="generation failed"):
        await pipeline.run(query.id)

    assert session.committed_statuses == ["running", "failed"]
    assert query.status == "failed"
    assert query.error_message == "generation failed"

    channel = f"query:{query.id}:events"
    assert [published_channel for published_channel, _ in redis.published] == [
        channel,
        channel,
    ]

    first_event = json.loads(redis.published[0][1])
    second_event = json.loads(redis.published[1][1])

    assert first_event == {"event": "route_selected", "data": {"route": "simple"}}
    assert second_event == {
        "event": "error",
        "data": {"message": "generation failed"},
    }


@pytest.mark.asyncio
async def test_query_pipeline_run_generates_sentence_events_and_persists_answer_graph() -> (
    None
):
    from app.application.query_pipeline.query_pipeline import QueryPipeline
    from app.infrastructure.db.models import (
        Answer,
        SentenceTrace,
        SentenceTraceEvidence,
    )

    first_id = uuid.uuid4()
    second_id = uuid.uuid4()

    class _Point:
        def __init__(self, evidence_id: uuid.UUID, score: float) -> None:
            self.payload = {"evidence_id": str(evidence_id)}
            self.score = score

    query = _make_query()
    evidence_by_id = {
        first_id: SimpleNamespace(content="first evidence chunk"),
        second_id: SimpleNamespace(content="second evidence chunk"),
    }
    session = _FakeSession(query, evidence_by_id=evidence_by_id)
    redis = _FakeRedis()
    embedding_client = _FakeEmbeddingClient([[0.1, 0.2]])
    qdrant_store = _FakeQdrantStore(
        {
            "dense": [],
            "sparse": [],
            "fused": [_Point(first_id, 0.61), _Point(second_id, 0.58)],
        }
    )
    rerank_client = _FakeRerankClient(
        [
            RerankResult(index=1, relevance_score=0.95),
            RerankResult(index=0, relevance_score=0.72),
        ]
    )
    llm_client = _FakeLLMClient(
        [
            '[{"sentence":"First sentence.","evidence_ids":["',
            '{sid}"]}},{{"sentence":"Second sentence.","evidence_ids":["{fid}","{sid}"]}}]'.format(
                sid=second_id,
                fid=first_id,
            ),
        ]
    )

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
        embedding_client=embedding_client,
        qdrant_store=qdrant_store,
        rerank_client=rerank_client,
        llm_client=llm_client,
    )

    await pipeline.run(query.id)

    assert len(llm_client.calls) == 1

    answers = [obj for obj in session.added_objects if isinstance(obj, Answer)]
    traces = [obj for obj in session.added_objects if isinstance(obj, SentenceTrace)]
    links = [
        obj for obj in session.added_objects if isinstance(obj, SentenceTraceEvidence)
    ]

    assert len(answers) == 1
    assert answers[0].query_id == query.id
    assert answers[0].full_text == "First sentence. Second sentence."

    assert [(trace.sentence_index, trace.sentence_text) for trace in traces] == [
        (0, "First sentence."),
        (1, "Second sentence."),
    ]
    assert [(link.evidence_id, link.citation_index) for link in links] == [
        (second_id, 0),
        (first_id, 0),
        (second_id, 1),
    ]

    events = [json.loads(message) for _, message in redis.published]
    assert events == [
        {"event": "route_selected", "data": {"route": "simple"}},
        {"event": "retrieving", "data": {"status": "retrieving"}},
        {"event": "generating", "data": {"sentence": "First sentence."}},
        {"event": "generating", "data": {"sentence": "Second sentence."}},
        {
            "event": "done",
            "data": {
                "id": str(answers[0].id),
                "query_id": str(query.id),
                "full_text": "First sentence. Second sentence.",
                "sentences": [
                    {
                        "sentence_index": 0,
                        "sentence_text": "First sentence.",
                        "evidence_ids": [str(second_id)],
                    },
                    {
                        "sentence_index": 1,
                        "sentence_text": "Second sentence.",
                        "evidence_ids": [str(first_id), str(second_id)],
                    },
                ],
                "evidence": [
                    {
                        "id": str(second_id),
                        "content": "second evidence chunk",
                    },
                    {
                        "id": str(first_id),
                        "content": "first evidence chunk",
                    },
                ],
            },
        },
    ]
