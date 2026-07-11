from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.schemas.threads import (
    SentenceTraceFeedbackRequest,
    SentenceTraceFeedbackResponse,
)
from app.application.query_pipeline.erm import apply_feedback_to_erm
from app.infrastructure.db.models import Answer, Message, Segment

router = APIRouter(prefix="/api/v1/sentence-traces", tags=["sentence-traces"])


@router.put("/{trace_id}/rating", response_model=SentenceTraceFeedbackResponse)
async def put_sentence_trace_rating(
    trace_id: UUID,
    payload: SentenceTraceFeedbackRequest,
    request: Request,
) -> SentenceTraceFeedbackResponse:
    embedding_client = getattr(request.app.state, "embedding_client", None)
    if embedding_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Feedback processing is unavailable"},
        )

    async with request.app.state.session_factory() as session:
        trace = await session.scalar(
            select(Segment)
            .options(
                selectinload(Segment.answer)
                .selectinload(Answer.message)
                .selectinload(Message.reply_to_message)
            )
            .where(Segment.id == trace_id)
        )
        if trace is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Sentence trace not found"},
            )

        previous_rating = trace.rating
        if previous_rating != payload.rating:
            trace.rating = payload.rating
            assistant_message = trace.answer.message
            user_message = assistant_message.reply_to_message
            if user_message is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"message": "The trace is not attached to a user message"},
                )

            evidence_ids = [
                UUID(evidence_id) if not isinstance(evidence_id, UUID) else evidence_id
                for evidence_id in trace.evidence_ids
            ]
            await apply_feedback_to_erm(
                session,
                query_text=user_message.content_text,
                evidence_ids=evidence_ids,
                previous_rating=previous_rating,
                next_rating=payload.rating,
                embedding_client=embedding_client,
            )

        await session.commit()

    return SentenceTraceFeedbackResponse(trace_id=trace_id, rating=payload.rating)
