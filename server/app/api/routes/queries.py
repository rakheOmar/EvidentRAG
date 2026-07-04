from __future__ import annotations

from uuid import UUID

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.schemas.queries import (
    AnswerResponse,
    EvidenceResponse,
    PendingAnswerResponse,
    QueryCreate,
    QueryResponse,
    SentenceTraceResponse,
)
from app.api.sse.sse import redis_pubsub_stream, sse_event
from app.infrastructure.db.models import (
    Answer,
    Evidence,
    Query,
    SentenceTrace,
    SentenceTraceEvidence,
)

router = APIRouter(prefix="/api/v1/queries", tags=["queries"])


async def _build_answer_response(session, query_id: UUID) -> AnswerResponse | None:
    answer = await session.scalar(
        select(Answer)
        .options(
            selectinload(Answer.sentence_traces)
            .selectinload(SentenceTrace.evidence_links)
            .selectinload(SentenceTraceEvidence.evidence),
            selectinload(Answer.sentence_traces)
            .selectinload(SentenceTrace.evidence_links)
            .selectinload(SentenceTraceEvidence.evidence)
            .selectinload(Evidence.document),
        )
        .where(Answer.query_id == query_id)
    )
    if answer is None:
        return None

    evidence_by_id: dict[UUID, EvidenceResponse] = {}
    sentences: list[SentenceTraceResponse] = []

    for trace in sorted(answer.sentence_traces, key=lambda item: item.sentence_index):
        ordered_links = sorted(
            trace.evidence_links, key=lambda item: item.citation_index
        )
        evidence_ids: list[UUID] = []
        for link in ordered_links:
            evidence_ids.append(link.evidence_id)
            evidence = link.evidence
            evidence_by_id.setdefault(
                evidence.id,
                EvidenceResponse(
                    id=evidence.id,
                    content=evidence.content,
                    context_header=evidence.context_header,
                    document_title=evidence.document.title,
                    document_slug=evidence.document.slug,
                    page=evidence.page,
                ),
            )

        sentences.append(
            SentenceTraceResponse(
                sentence_index=trace.sentence_index,
                sentence_text=trace.sentence_text,
                evidence_ids=evidence_ids,
            )
        )

    return AnswerResponse(
        id=answer.id,
        query_id=answer.query_id,
        full_text=answer.full_text,
        sentences=sentences,
        evidence=list(evidence_by_id.values()),
    )


async def _replay_terminal_query_event(request: Request, query_id: UUID) -> str | None:
    async with request.app.state.session_factory() as session:
        query = await session.get(Query, query_id)
        if query is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        if query.status == "failed":
            return sse_event(
                "error", {"message": query.error_message or "Query failed"}
            )

        if query.status != "completed":
            return None

        answer = await _build_answer_response(session, query_id)
        if answer is None:
            return sse_event("done", {"status": "completed"})

        return sse_event("done", answer.model_dump(mode="json"))


async def _query_events_stream(request: Request, query_id: UUID) -> AsyncIterator[str]:
    replayed_event = await _replay_terminal_query_event(request, query_id)
    if replayed_event is not None:
        yield replayed_event
        return

    channel = f"query:{query_id}:events"
    async for event in redis_pubsub_stream(request.app.state.redis, channel):
        yield event


@router.post("", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def create_query(payload: QueryCreate, request: Request) -> Query:
    async with request.app.state.session_factory() as session:
        query = Query(query_text=payload.query_text)
        session.add(query)
        await session.commit()
        await session.refresh(query)

    job_queue = getattr(request.app.state, "job_queue", None)
    if job_queue is not None:
        await job_queue.enqueue_job("run_query_pipeline", str(query.id))

    return query


@router.get("", response_model=list[QueryResponse])
async def list_queries(
    request: Request, limit: int = 100, offset: int = 0
) -> list[Query]:
    async with request.app.state.session_factory() as session:
        result = await session.execute(
            select(Query).order_by(Query.created_at).offset(offset).limit(limit)
        )
        return list(result.scalars())


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(query_id: UUID, request: Request) -> Query:
    async with request.app.state.session_factory() as session:
        query = await session.get(Query, query_id)
        if query is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return query


@router.get("/{query_id}/answer", response_model=PendingAnswerResponse | AnswerResponse)
async def get_query_answer(
    query_id: UUID, request: Request, response: Response
) -> PendingAnswerResponse | AnswerResponse:
    async with request.app.state.session_factory() as session:
        query = await session.get(Query, query_id)
        if query is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        answer = await _build_answer_response(session, query_id)
        if answer is None:
            response.status_code = status.HTTP_202_ACCEPTED
            return PendingAnswerResponse(status="pending")

        return answer


@router.get("/{query_id}/events")
async def get_query_events(query_id: UUID, request: Request) -> StreamingResponse:
    return StreamingResponse(
        _query_events_stream(request, query_id),
        media_type="text/event-stream",
    )
