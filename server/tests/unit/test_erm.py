from __future__ import annotations

import uuid

import pytest

from app.application.query_pipeline.erm import (
    apply_feedback_to_erm,
    cosine_similarity,
    hash_query_embedding,
    load_erm_adjustments,
    multiplier_from_totals,
    score_rating_delta,
)
from app.infrastructure.db.models import ErmQueryEmbedding, ErmScore


class _FakeScalarResult:
    def __init__(self, values) -> None:
        self._values = values

    def scalars(self):
        return self._values


class _FakeReadSession:
    def __init__(self, rows: list[ErmScore]) -> None:
        self._rows = rows

    async def execute(self, _statement):
        return _FakeScalarResult(self._rows)


class _FakeWriteSession:
    def __init__(self) -> None:
        self.embeddings: dict[str, ErmQueryEmbedding] = {}
        self.scores: dict[tuple[str, uuid.UUID], ErmScore] = {}

    async def get(self, model, identity):
        if model is ErmQueryEmbedding:
            return self.embeddings.get(identity)
        if model is ErmScore:
            key = (identity["query_embedding_hash"], identity["evidence_id"])
            return self.scores.get(key)
        raise AssertionError(f"Unexpected model lookup: {model}")

    def add(self, obj) -> None:
        if isinstance(obj, ErmQueryEmbedding):
            self.embeddings[obj.query_embedding_hash] = obj
        elif isinstance(obj, ErmScore):
            self.scores[(obj.query_embedding_hash, obj.evidence_id)] = obj
        else:
            raise AssertionError(f"Unexpected object added: {obj}")

    async def flush(self) -> None:
        return None


class _FakeEmbeddingClient:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["What is BERT?"]
        return [[1.0, 0.0]]


def test_score_rating_delta_is_idempotent_for_same_rating() -> None:
    assert score_rating_delta("up", "up") == (0.0, 0.0)
    assert score_rating_delta("down", "down") == (0.0, 0.0)


def test_score_rating_delta_flips_previous_vote() -> None:
    assert score_rating_delta("up", "down") == (-1.0, 1.0)
    assert score_rating_delta("down", "up") == (1.0, -1.0)


def test_multiplier_from_totals_boosts_and_penalizes() -> None:
    boosted = multiplier_from_totals(2.0, 0.0)
    penalized = multiplier_from_totals(0.0, 2.0)

    assert boosted.state == "boost"
    assert boosted.multiplier > 1.0
    assert penalized.state == "penalty"
    assert penalized.multiplier < 1.0


def test_cosine_similarity_handles_zero_and_perfect_match() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


@pytest.mark.asyncio
async def test_load_erm_adjustments_applies_similarity_threshold_and_weighting() -> (
    None
):
    evidence_id = uuid.uuid4()
    matching_hash = hash_query_embedding([1.0, 0.0])
    weak_hash = hash_query_embedding([0.0, 1.0])

    rows = [
        ErmScore(
            query_embedding_hash=matching_hash,
            evidence_id=evidence_id,
            boost_score=2.0,
            penalty_score=0.0,
            query_embedding=ErmQueryEmbedding(
                query_embedding_hash=matching_hash,
                embedding=[1.0, 0.0],
            ),
        ),
        ErmScore(
            query_embedding_hash=weak_hash,
            evidence_id=evidence_id,
            boost_score=10.0,
            penalty_score=0.0,
            query_embedding=ErmQueryEmbedding(
                query_embedding_hash=weak_hash,
                embedding=[0.0, 1.0],
            ),
        ),
    ]

    adjustments = await load_erm_adjustments(
        _FakeReadSession(rows),
        query_embedding=[1.0, 0.0],
        evidence_ids=[evidence_id],
    )

    adjustment = adjustments[evidence_id]
    assert adjustment.state == "boost"
    assert adjustment.multiplier == pytest.approx(1.3)


@pytest.mark.asyncio
async def test_apply_feedback_to_erm_creates_and_updates_scores() -> None:
    session = _FakeWriteSession()
    evidence_id = uuid.uuid4()

    await apply_feedback_to_erm(
        session,
        query_text="What is BERT?",
        evidence_ids=[evidence_id],
        previous_rating=None,
        next_rating="up",
        embedding_client=_FakeEmbeddingClient(),
    )
    await apply_feedback_to_erm(
        session,
        query_text="What is BERT?",
        evidence_ids=[evidence_id],
        previous_rating="up",
        next_rating="down",
        embedding_client=_FakeEmbeddingClient(),
    )

    query_hash = hash_query_embedding([1.0, 0.0])
    score = session.scores[(query_hash, evidence_id)]
    assert score.boost_score == 0.0
    assert score.penalty_score == 1.0
