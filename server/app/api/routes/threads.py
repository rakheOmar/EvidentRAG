from __future__ import annotations

import re
from collections.abc import AsyncIterator
from typing import Literal, cast
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
from app.core.logging import enrich_wide_event
from app.core.telemetry import inject_job_context
from app.core.telemetry import record_degradation
from app.infrastructure.db.models import (
    Answer,
    Evidence,
    Message,
    Thread,
)

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])

_MARKDOWN_LINK_PATTERN = re.compile(r"!?\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_PREFIX_PATTERN = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*|>\s*|[-+*]\s+|\d+[.)]\s+|```\w*\s*)"
)
_MARKDOWN_TOKEN_PATTERN = re.compile(r"[`*_~|]")
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _plain_thread_title(value: str) -> str:
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = _MARKDOWN_LINK_PATTERN.sub(r"\1", line)
        line = _MARKDOWN_PREFIX_PATTERN.sub("", line)
        line = _HTML_TAG_PATTERN.sub("", line)
        line = _MARKDOWN_TOKEN_PATTERN.sub("", line)
        line = _WHITESPACE_PATTERN.sub(" ", line).strip().strip("\"'")
        if line:
            return line[:80].rstrip()
    return ""


async def _generate_thread_title(request: Request, content: str) -> str:
    llm_client = getattr(request.app.state, "llm_client", None)
    fallback = _plain_thread_title(content) or "New Chat"
    if llm_client is None:
        return fallback

    messages = [
        {
            "role": "system",
            "content": (
                "Generate a concise chat thread title for the user's opening "
                "message. Return exactly one line of plain text under 8 words. "
                "Do not use Markdown, headings, bullets, pipes, code fences, "
                "asterisks, underscores, brackets, or quotes."
            ),
        },
        {"role": "user", "content": content},
    ]

    try:
        title = _plain_thread_title(await llm_client.generate(messages))
    except Exception:
        return fallback

    return title or fallback


async def _build_answer_response(
    session, message: Message, answer: Answer | None = None
) -> AnswerResponse | None:
    if answer is None:
        answer = await session.scalar(
            select(Answer)
            .options(selectinload(Answer.segments))
            .where(Answer.message_id == message.id)
        )
    if answer is None:
        return None

    evidence_metadata = (
        answer.extra.get("evidence_metadata", {})
        if isinstance(answer.extra, dict)
        else {}
    )
    evidence_by_id: dict[UUID, EvidenceResponse] = {}

    ordered_segments = sorted(answer.segments, key=lambda item: item.segment_index)
    segment_evidence_ids: dict[UUID, list[UUID]] = {}
    referenced_ids: set[UUID] = set()
    for seg in ordered_segments:
        resolved: list[UUID] = []
        for eid in seg.evidence_ids:
            try:
                parsed_eid = UUID(eid) if not isinstance(eid, UUID) else eid
            except (ValueError, AttributeError) as exc:
                record_degradation(
                    "answer_segment_evidence_id",
                    segment_id=str(seg.id),
                    error_type=type(exc).__name__,
                )
                continue
            resolved.append(parsed_eid)
            referenced_ids.add(parsed_eid)
        segment_evidence_ids[seg.id] = resolved

    retrieved_evidence_ids = (
        answer.extra.get("retrieved_evidence_ids", [])
        if isinstance(answer.extra, dict)
        else []
    )
    for raw_eid in retrieved_evidence_ids:
        try:
            referenced_ids.add(UUID(str(raw_eid)))
        except ValueError:
            continue

    if referenced_ids:
        evidence_rows = await session.scalars(
            select(Evidence)
            .options(selectinload(Evidence.document))
            .where(Evidence.id.in_(referenced_ids))
        )
        for evidence in evidence_rows:
            asset_key = (evidence.extra or {}).get("asset_key")
            evidence_by_id[evidence.id] = EvidenceResponse(
                id=evidence.id,
                content=evidence.content,
                context_header=evidence.context_header,
                document_title=evidence.document.title,
                document_slug=evidence.document.slug,
                page=evidence.page,
                erm_state=(evidence_metadata.get(str(evidence.id), {}) or {}).get(
                    "erm_state"
                ),
                erm_multiplier=(evidence_metadata.get(str(evidence.id), {}) or {}).get(
                    "erm_multiplier"
                ),
                kind=(evidence.extra or {}).get("kind", "text"),
                asset_key=asset_key,
                asset_url=(
                    f"/api/v1/documents/{evidence.document_id}/assets/"
                    f"{str(asset_key).rsplit('/', 1)[-1]}"
                    if asset_key
                    else None
                ),
                bounding_box=(evidence.extra or {}).get("bounding_box"),
            )

    segments = [
        SegmentResponse(
            id=seg.id,
            segment_index=seg.segment_index,
            text=seg.text,
            evidence_ids=segment_evidence_ids[seg.id],
            rating=cast(Literal["up", "down"] | None, seg.rating),
        )
        for seg in ordered_segments
    ]

    evidence_dicts = [
        {
            "id": str(ev.id),
            "content": ev.content,
            "document_title": ev.document_title,
            "document_slug": ev.document_slug,
            "page": ev.page,
            "context_header": ev.context_header,
            "kind": ev.kind,
            "asset_key": ev.asset_key,
            "asset_url": ev.asset_url,
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


async def _build_message_response(
    session, message: Message, answer: Answer | None = None
) -> MessageResponse:
    answer_response = (
        await _build_answer_response(session, message, answer)
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
        answer=answer_response,
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
    async def replay_after_subscribe() -> tuple[list[str], bool]:
        replayed_event = await _replay_terminal_message_event(
            request, thread_id, message_id
        )
        return (
            [replayed_event] if replayed_event is not None else [],
            replayed_event is not None,
        )

    channel = f"message:{message_id}:events"
    async for event in redis_pubsub_stream(
        request.app.state.redis,
        channel,
        replay_after_subscribe,
    ):
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
    if job_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Message processing is unavailable"},
        )
    await job_queue.enqueue_job(
        "run_message_pipeline", str(assistant_message.id), inject_job_context()
    )
    enrich_wide_event(
        action="thread.create",
        thread={
            "id": str(thread.id),
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "content_length": len(payload.content),
        },
    )

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
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "limit must be 1..100 and offset must be non-negative"},
        )
    async with request.app.state.session_factory() as session:
        result = await session.execute(
            select(Thread)
            .order_by(Thread.updated_at.desc(), Thread.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        threads = [_thread_summary_response(thread) for thread in result.scalars()]
        enrich_wide_event(
            action="thread.list",
            result_count=len(threads),
            pagination={"limit": limit, "offset": offset},
        )
        return threads


@router.get("/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(thread_id: UUID, request: Request) -> ThreadDetailResponse:
    async with request.app.state.session_factory() as session:
        thread = await session.scalar(
            select(Thread)
            .options(selectinload(Thread.messages))
            .where(Thread.id == thread_id)
        )
        if thread is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Thread not found"},
            )

        ordered_messages = sorted(thread.messages, key=lambda message: message.position)
        enrich_wide_event(
            action="thread.get",
            thread={"id": str(thread_id), "message_count": len(ordered_messages)},
        )
        assistant_message_ids = [
            message.id for message in ordered_messages if message.role == "assistant"
        ]
        answer_by_message_id: dict[UUID, Answer] = {}
        if assistant_message_ids:
            answer_rows = await session.scalars(
                select(Answer)
                .options(selectinload(Answer.segments))
                .where(Answer.message_id.in_(assistant_message_ids))
            )
            answer_by_message_id = {row.message_id: row for row in answer_rows}

        return ThreadDetailResponse(
            **_thread_summary_response(thread).model_dump(),
            messages=[
                await _build_message_response(
                    session, message, answer_by_message_id.get(message.id)
                )
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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Thread not found"},
            )
        user_message, assistant_message = await _create_turn(
            session, thread=thread, content=payload.content
        )
        await session.commit()
        await session.refresh(thread)
        await session.refresh(user_message)
        await session.refresh(assistant_message)

    job_queue = getattr(request.app.state, "job_queue", None)
    if job_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"message": "Message processing is unavailable"},
        )
    await job_queue.enqueue_job(
        "run_message_pipeline", str(assistant_message.id), inject_job_context()
    )
    enrich_wide_event(
        action="thread.message.create",
        thread={
            "id": str(thread_id),
            "user_message_id": str(user_message.id),
            "assistant_message_id": str(assistant_message.id),
            "content_length": len(payload.content),
        },
    )

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
    enrich_wide_event(
        action="thread.message.events",
        thread={"id": str(thread_id), "message_id": str(message_id)},
    )
    return StreamingResponse(
        _message_events_stream(request, thread_id, message_id),
        media_type="text/event-stream",
    )
