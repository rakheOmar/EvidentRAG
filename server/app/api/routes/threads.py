from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.schemas.threads import (
    AnswerResponse,
    EvidenceResponse,
    MessageCreate,
    MessageResponse,
    SegmentResponse,
    ThreadCreate,
    ThreadDetailResponse,
    ThreadSummaryResponse,
    ThreadTurnResponse,
)
from app.api.sse.sse import redis_pubsub_stream, sse_event
from app.application.query_pipeline.content_parts import answer_content_parts
from app.infrastructure.db.models import (
    Answer,
    Evidence,
    Message,
    Thread,
)

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])

logger = logging.getLogger(__name__)


async def _generate_thread_title(request: Request, content: str) -> str:
    llm_client = getattr(request.app.state, "llm_client", None)
    fallback = content.strip().replace("\n", " ")[:60] or "New Chat"
    if llm_client is None:
        return fallback

    messages = [
        {
            "role": "system",
            "content": (
                "Generate a concise chat thread title for the user's opening "
                "message. Return plain text only, under 8 words, with no quotes."
            ),
        },
        {"role": "user", "content": content},
    ]

    try:
        title = (await llm_client.generate(messages)).strip().strip('"').strip()
    except Exception:
        return fallback

    return title[:80] if title else fallback


async def _build_answer_response(session, message: Message) -> AnswerResponse | None:
    answer = await session.scalar(
        select(Answer)
        .options(selectinload(Answer.segments))
        .where(Answer.message_id == message.id)
    )
    if answer is None:
        return None

    evidence_by_id: dict[UUID, EvidenceResponse] = {}
    segments: list[SegmentResponse] = []
    evidence_metadata = (
        answer.extra.get("evidence_metadata", {})
        if isinstance(answer.extra, dict)
        else {}
    )

    for seg in sorted(answer.segments, key=lambda item: item.segment_index):
        resolved_evidence: list[UUID] = []
        for eid in seg.evidence_ids:
            try:
                parsed_eid = UUID(eid) if not isinstance(eid, UUID) else eid
            except (ValueError, AttributeError) as exc:
                logger.info(
                    "answer_segment_evidence_id_skipped",
                    extra={
                        "wide_event": {
                            "event": "answer_segment_evidence_id_skipped",
                            "segment_id": str(seg.id),
                            "raw_evidence_id": str(eid),
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "outcome": "skipped",
                        }
                    },
                )
                continue
            resolved_evidence.append(parsed_eid)
            if parsed_eid not in evidence_by_id:
                evidence = await session.scalar(
                    select(Evidence)
                    .options(selectinload(Evidence.document))
                    .where(Evidence.id == parsed_eid)
                )
                if evidence is not None:
                    evidence_by_id[parsed_eid] = EvidenceResponse(
                        id=evidence.id,
                        content=evidence.content,
                        context_header=evidence.context_header,
                        document_title=evidence.document.title,
                        document_slug=evidence.document.slug,
                        page=evidence.page,
                        erm_state=(
                            evidence_metadata.get(str(parsed_eid), {}) or {}
                        ).get("erm_state"),
                        erm_multiplier=(
                            evidence_metadata.get(str(parsed_eid), {}) or {}
                        ).get("erm_multiplier"),
                    )

        segments.append(
            SegmentResponse(
                id=seg.id,
                segment_index=seg.segment_index,
                text=seg.text,
                evidence_ids=resolved_evidence,
                rating=seg.rating,
            )
        )

    evidence_dicts = [
        {
            "id": str(ev.id),
            "content": ev.content,
            "document_title": ev.document_title,
            "document_slug": ev.document_slug,
            "page": ev.page,
            "context_header": ev.context_header,
        }
        for ev in evidence_by_id.values()
    ]

    return AnswerResponse(
        id=answer.id,
        message_id=answer.message_id,
        full_text=answer.full_text,
        reasoning_trace=answer.reasoning_trace or [],
        segments=segments,
        evidence=list(evidence_by_id.values()),
        content_parts=answer_content_parts(answer.full_text, evidence_dicts),
        context_usage=(
            answer.extra.get("context_usage")
            if isinstance(answer.extra, dict)
            else None
        ),
    )


async def _build_message_response(session, message: Message) -> MessageResponse:
    answer = (
        await _build_answer_response(session, message)
        if message.role == "assistant"
        else None
    )
    return MessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        reply_to_message_id=message.reply_to_message_id,
        position=message.position,
        role=message.role,
        content_text=answer.full_text if answer is not None else message.content_text,
        status=message.status,
        selected_route=message.selected_route,
        sub_queries=list(message.sub_queries or []),
        error_message=message.error_message,
        created_at=message.created_at,
        updated_at=message.updated_at,
        completed_at=message.completed_at,
        answer=answer,
    )


def _thread_summary_response(thread: Thread) -> ThreadSummaryResponse:
    return ThreadSummaryResponse(
        id=thread.id,
        title=thread.title,
        summary=thread.summary,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


async def _thread_turn_response(
    session, thread: Thread, user_message: Message, assistant_message: Message
) -> ThreadTurnResponse:
    return ThreadTurnResponse(
        thread=_thread_summary_response(thread),
        user_message=await _build_message_response(session, user_message),
        assistant_message=await _build_message_response(session, assistant_message),
    )


async def _replay_terminal_message_event(
    request: Request, thread_id: UUID, message_id: UUID
) -> str | None:
    async with request.app.state.session_factory() as session:
        message = await session.scalar(
            select(Message).where(
                Message.id == message_id, Message.thread_id == thread_id
            )
        )
        if message is None or message.role != "assistant":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        if message.status == "failed":
            return sse_event(
                "done",
                {
                    "thread_id": str(thread_id),
                    "message_id": str(message.id),
                    "content_parts": [],
                    "error": True,
                    "error_message": message.error_message or "Message failed",
                },
            )

        if message.status != "completed":
            return None

        answer = await _build_answer_response(session, message)
        if answer is None:
            return sse_event(
                "done",
                {
                    "thread_id": str(thread_id),
                    "message_id": str(message.id),
                    "content_parts": [],
                    "error": False,
                },
            )

        payload = answer.model_dump(mode="json")
        payload["thread_id"] = str(thread_id)
        payload["message_id"] = str(message.id)
        payload["error"] = False
        return sse_event("done", payload)


async def _message_events_stream(
    request: Request, thread_id: UUID, message_id: UUID
) -> AsyncIterator[str]:
    replayed_event = await _replay_terminal_message_event(
        request, thread_id, message_id
    )
    if replayed_event is not None:
        yield replayed_event
        return

    channel = f"message:{message_id}:events"
    async for event in redis_pubsub_stream(request.app.state.redis, channel):
        yield event


async def _next_position(session, thread_id: UUID) -> int:
    return (
        await session.scalar(
            select(func.coalesce(func.max(Message.position) + 1, 0)).where(
                Message.thread_id == thread_id
            )
        )
    ) or 0


async def _create_turn(
    session, *, thread: Thread, content: str
) -> tuple[Message, Message]:
    user_position = await _next_position(session, thread.id)
    user_message = Message(
        thread_id=thread.id,
        position=user_position,
        role="user",
        content_text=content,
        status="completed",
    )
    session.add(user_message)
    await session.flush()

    assistant_message = Message(
        thread_id=thread.id,
        reply_to_message_id=user_message.id,
        position=user_position + 1,
        role="assistant",
        content_text="",
        status="pending",
        sub_queries=[],
    )
    session.add(assistant_message)
    await session.flush()
    return user_message, assistant_message


@router.post("", response_model=ThreadTurnResponse, status_code=status.HTTP_201_CREATED)
async def create_thread(payload: ThreadCreate, request: Request) -> ThreadTurnResponse:
    async with request.app.state.session_factory() as session:
        thread = Thread(
            title=await _generate_thread_title(request, payload.content),
            summary="",
        )
        session.add(thread)
        await session.flush()
        user_message, assistant_message = await _create_turn(
            session, thread=thread, content=payload.content
        )
        await session.commit()
        await session.refresh(thread)
        await session.refresh(user_message)
        await session.refresh(assistant_message)

    job_queue = getattr(request.app.state, "job_queue", None)
    if job_queue is not None:
        await job_queue.enqueue_job("run_message_pipeline", str(assistant_message.id))

    async with request.app.state.session_factory() as session:
        thread = await session.get(Thread, thread.id)
        user_message = await session.get(Message, user_message.id)
        assistant_message = await session.get(Message, assistant_message.id)
        if thread is None or user_message is None or assistant_message is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return await _thread_turn_response(
            session, thread, user_message, assistant_message
        )


@router.get("", response_model=list[ThreadSummaryResponse])
async def list_threads(
    request: Request, limit: int = 100, offset: int = 0
) -> list[ThreadSummaryResponse]:
    async with request.app.state.session_factory() as session:
        result = await session.execute(
            select(Thread)
            .order_by(Thread.updated_at.desc(), Thread.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [_thread_summary_response(thread) for thread in result.scalars()]


@router.get("/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(thread_id: UUID, request: Request) -> ThreadDetailResponse:
    async with request.app.state.session_factory() as session:
        thread = await session.scalar(
            select(Thread)
            .options(selectinload(Thread.messages))
            .where(Thread.id == thread_id)
        )
        if thread is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        ordered_messages = sorted(thread.messages, key=lambda message: message.position)
        return ThreadDetailResponse(
            **_thread_summary_response(thread).model_dump(),
            messages=[
                await _build_message_response(session, message)
                for message in ordered_messages
            ],
        )


@router.post(
    "/{thread_id}/messages",
    response_model=ThreadTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def append_message(
    thread_id: UUID, payload: MessageCreate, request: Request
) -> ThreadTurnResponse:
    async with request.app.state.session_factory() as session:
        thread = await session.get(Thread, thread_id)
        if thread is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        user_message, assistant_message = await _create_turn(
            session, thread=thread, content=payload.content
        )
        await session.commit()
        await session.refresh(thread)
        await session.refresh(user_message)
        await session.refresh(assistant_message)

    job_queue = getattr(request.app.state, "job_queue", None)
    if job_queue is not None:
        await job_queue.enqueue_job("run_message_pipeline", str(assistant_message.id))

    async with request.app.state.session_factory() as session:
        thread = await session.get(Thread, thread_id)
        user_message = await session.get(Message, user_message.id)
        assistant_message = await session.get(Message, assistant_message.id)
        if thread is None or user_message is None or assistant_message is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return await _thread_turn_response(
            session, thread, user_message, assistant_message
        )


@router.get("/{thread_id}/messages/{message_id}/events")
async def get_message_events(
    thread_id: UUID, message_id: UUID, request: Request
) -> StreamingResponse:
    return StreamingResponse(
        _message_events_stream(request, thread_id, message_id),
        media_type="text/event-stream",
    )
