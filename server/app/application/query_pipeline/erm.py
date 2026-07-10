from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.infrastructure.db.models import ErmQueryEmbedding, ErmScore

SIMILARITY_THRESHOLD = 0.80
ERM_MULTIPLIER_MIN = 0.25
ERM_MULTIPLIER_MAX = 2.0
ERM_MULTIPLIER_STEP = 0.15


Rating = Literal["up", "down"]
ErmState = Literal["boost", "penalty"]


@dataclass(frozen=True)
class ErmAdjustment:
    multiplier: float
    state: ErmState | None


def hash_query_embedding(embedding: list[float]) -> str:
    payload = ",".join(f"{value:.8f}" for value in embedding)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def score_rating_delta(
    previous_rating: Rating | None, next_rating: Rating
) -> tuple[float, float]:
    boost_delta = 0.0
    penalty_delta = 0.0

    if previous_rating == "up":
        boost_delta -= 1.0
    elif previous_rating == "down":
        penalty_delta -= 1.0

    if next_rating == "up":
        boost_delta += 1.0
    else:
        penalty_delta += 1.0

    return boost_delta, penalty_delta


def multiplier_from_totals(boost_total: float, penalty_total: float) -> ErmAdjustment:
    net = boost_total - penalty_total
    if abs(net) < 1e-9:
        return ErmAdjustment(multiplier=1.0, state=None)

    multiplier = 1.0 + (net * ERM_MULTIPLIER_STEP)
    multiplier = max(ERM_MULTIPLIER_MIN, min(ERM_MULTIPLIER_MAX, multiplier))
    state: ErmState = "boost" if multiplier > 1.0 else "penalty"
    return ErmAdjustment(multiplier=multiplier, state=state)


async def apply_feedback_to_erm(
    session,
    *,
    query_text: str,
    evidence_ids: list[uuid.UUID],
    previous_rating: Rating | None,
    next_rating: Rating,
    embedding_client,
) -> None:
    if not evidence_ids:
        return

    embedding = embedding_client.embed_texts([query_text])[0]
    query_embedding_hash = hash_query_embedding(embedding)
    query_embedding = await session.get(ErmQueryEmbedding, query_embedding_hash)
    if query_embedding is None:
        query_embedding = ErmQueryEmbedding(
            query_embedding_hash=query_embedding_hash,
            embedding=embedding,
        )
        session.add(query_embedding)
        await session.flush()

    boost_delta, penalty_delta = score_rating_delta(previous_rating, next_rating)

    for evidence_id in evidence_ids:
        score = await session.get(
            ErmScore,
            {
                "query_embedding_hash": query_embedding_hash,
                "evidence_id": evidence_id,
            },
        )
        if score is None:
            score = ErmScore(
                query_embedding_hash=query_embedding_hash,
                evidence_id=evidence_id,
                boost_score=0.0,
                penalty_score=0.0,
            )
            session.add(score)

        score.boost_score = max(0.0, score.boost_score + boost_delta)
        score.penalty_score = max(0.0, score.penalty_score + penalty_delta)


async def load_erm_adjustments(
    session,
    *,
    query_embedding: list[float],
    evidence_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ErmAdjustment]:
    if not evidence_ids:
        return {}

    result = await session.execute(
        select(ErmScore)
        .options(selectinload(ErmScore.query_embedding))
        .where(ErmScore.evidence_id.in_(evidence_ids))
    )

    totals: dict[uuid.UUID, tuple[float, float]] = {}
    for score in result.scalars():
        similarity = cosine_similarity(query_embedding, score.query_embedding.embedding)
        if similarity < SIMILARITY_THRESHOLD:
            continue

        boost_total, penalty_total = totals.get(score.evidence_id, (0.0, 0.0))
        totals[score.evidence_id] = (
            boost_total + (similarity * score.boost_score),
            penalty_total + (similarity * score.penalty_score),
        )

    adjustments: dict[uuid.UUID, ErmAdjustment] = {}
    for evidence_id, (boost_total, penalty_total) in totals.items():
        adjustment = multiplier_from_totals(boost_total, penalty_total)
        if adjustment.state is None:
            continue
        adjustments[evidence_id] = adjustment
    return adjustments
