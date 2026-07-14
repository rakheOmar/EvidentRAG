from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from time import perf_counter
from typing import TypedDict, cast

import httpx

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.application.query_pipeline.content_parts import (
    answer_content_parts,
    reasoning_part,
    text_part,
)
from app.application.query_pipeline.erm import (
    ErmAdjustment,
    load_erm_adjustments,
)
from app.application.query_pipeline.json_stream_parser import (
    JsonStreamParser,
    join_segment_texts,
)
from app.core.logging import enrich_wide_event
from app.core.telemetry import record_degradation
from app.infrastructure.db.models import (
    Answer,
    Document,
    Evidence,
    Message,
    MessageEvidenceCandidate,
    Segment,
    Source,
    Thread,
)
from app.infrastructure.llm.context_manager import ContextManager


def _candidate_rows(by_id, evidence_ids: list[uuid.UUID]) -> list[dict[str, object]]:
    return [
        {
            "evidence_id": str(evidence_id),
            "document_title": by_id[evidence_id].document.title,
            "page": by_id[evidence_id].page,
            "snippet": by_id[evidence_id].content[:160],
        }
        for evidence_id in evidence_ids
    ]


class NonRetryablePipelineError(Exception):
    """Raised for conditions that cannot succeed on retry (e.g. the target
    message no longer exists). The worker should not re-enqueue these."""


class AnswerGenerationError(NonRetryablePipelineError):
    """Raised when the model cannot produce a usable structured answer."""


class NoRelevantEvidenceError(NonRetryablePipelineError):
    """Raised when retrieval found no eligible evidence for the query."""


class ConversationContext(TypedDict):
    conversation_history: str | None
    context_prefix: str | None
    effective_query_text: str


class RankedEvidenceResult(TypedDict):
    evidence_id: uuid.UUID
    index: int
    metadata: dict[str, object] | None
    score: float


MARKDOWN_SEGMENT_INSTRUCTION = (
    'Each object must have a "text" key and an "evidence_ids" key. '
    "Use one complete Markdown block or one plain-language sentence/phrase per object. "
    "Never split a Markdown construct across objects: headings, tables, lists, fenced code blocks, and display math must each remain structurally valid when objects are concatenated in order. "
    "Use blank lines around Markdown blocks, keep a table heading on its own line before its separator row, and keep every fenced code block complete in one object. "
    "Plain-language segments must use proper capitalization and punctuation. "
)


SIMPLE_SYSTEM_PROMPT = (
    "Answer the question using ONLY the provided evidence. "
    "If the evidence does not contain the answer, respond with [] (empty array). "
    "Respond ONLY with a valid JSON array and no other text. "
    "Do not include text outside the JSON array. Markdown is allowed inside text "
    "strings, including headings, lists, tables, fenced code blocks, and LaTeX math. "
    "Never emit Markdown image syntax; EvidentRAG attaches retrieved images itself. "
    "Escape JSON characters correctly. "
    + MARKDOWN_SEGMENT_INSTRUCTION
    + "Each evidence_ids value must list the evidence IDs that support its text. "
    "If a segment uses no evidence (e.g. connective text), use an empty array []. "
    "Example: "
    '[{"text": "This first claim", "evidence_ids": ["uuid1"]}, '
    '{"text": " is supported by different evidence.", "evidence_ids": ["uuid2"]}]'
)

MULTI_HOP_SYSTEM_PROMPT = (
    "Answer the original question using the chain of reasoning and evidence provided below. "
    "Synthesize the intermediate answers into a coherent final answer. "
    "Respond ONLY with a valid JSON array and no other text. "
    "Do not include text outside the JSON array. Markdown is allowed inside text "
    "strings, including headings, lists, tables, fenced code blocks, and LaTeX math. "
    "Never emit Markdown image syntax; EvidentRAG attaches retrieved images itself. "
    "Escape JSON characters correctly. "
    + MARKDOWN_SEGMENT_INSTRUCTION
    + "Each evidence_ids value must list the evidence IDs that support its text. "
    "If a segment uses no evidence (e.g. connective text), use an empty array []. "
    "Example: "
    '[{"text": "First finding", "evidence_ids": ["uuid1"]}, '
    '{"text": " which connects to", "evidence_ids": []}, '
    '{"text": " a second finding.", "evidence_ids": ["uuid2"]}]'
)

COMPARISON_SYSTEM_PROMPT = (
    "Compare the entities described in the question using the provided evidence. "
    "Highlight similarities and differences in a structured format. "
    "Respond ONLY with a valid JSON array and no other text. "
    "Do not include text outside the JSON array. Markdown is allowed inside text "
    "strings, including headings, lists, tables, fenced code blocks, and LaTeX math. "
    "Never emit Markdown image syntax; EvidentRAG attaches retrieved images itself. "
    "Escape JSON characters correctly. "
    + MARKDOWN_SEGMENT_INSTRUCTION
    + "Each evidence_ids value must list the evidence IDs that support its text. "
    "If a segment uses no evidence (e.g. connective text), use an empty array []. "
    "Example: "
    '[{"text": "Both approaches share", "evidence_ids": ["uuid1"]}, '
    '{"text": " but differ in", "evidence_ids": ["uuid2"]}]'
)

MAX_SUB_QUERIES = 4

MIN_EVENT_INTERVAL_S = 2.0

AGGREGATION_SYSTEM_PROMPT = (
    "Provide a comprehensive summary covering the main themes and key points "
    "from the provided evidence. Organize the summary by topic. "
    "Respond ONLY with a valid JSON array and no other text. "
    "Do not include text outside the JSON array. Markdown is allowed inside text "
    "strings, including headings, lists, tables, fenced code blocks, and LaTeX math. "
    "Never emit Markdown image syntax; EvidentRAG attaches retrieved images itself. "
    "Escape JSON characters correctly. "
    + MARKDOWN_SEGMENT_INSTRUCTION
    + "Each evidence_ids value must list the evidence IDs that support its text. "
    "If a segment uses no evidence (e.g. connective text), use an empty array []. "
    "Example: "
    '[{"text": "One key theme is", "evidence_ids": ["uuid1"]}, '
    '{"text": " which is supported by multiple sources.", "evidence_ids": ["uuid2", "uuid3"]}]'
)

CONVERSATION_SYSTEM_PROMPT = (
    "Answer the user's question using ONLY the provided conversation history and "
    "thread summary. Do not use external knowledge or retrieved documents. "
    "If the conversation history does not contain the answer, say that directly. "
    "Respond ONLY with a valid JSON array and no other text. "
    "Do not include text outside the JSON array. Markdown is allowed inside text "
    "strings, including headings, lists, tables, fenced code blocks, and LaTeX math. "
    "Never emit Markdown image syntax; EvidentRAG attaches retrieved images itself. "
    "Escape JSON characters correctly. "
    + MARKDOWN_SEGMENT_INSTRUCTION
    + "For conversation answers, always use [] for evidence_ids because the support comes from thread memory, not document evidence. "
    "If the user asks what questions they asked earlier, focus on prior user turns."
)


class QueryPipeline:
    def __init__(
        self,
        *,
        session_factory,
        redis,
        embedding_client=None,
        qdrant_store=None,
        rerank_client=None,
        llm_client=None,
        arag_router=None,
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._embedding_client = embedding_client
        self._qdrant_store = qdrant_store
        self._rerank_client = rerank_client
        self._llm_client = llm_client
        self._context_manager = getattr(
            llm_client, "context_manager", ContextManager("unknown")
        )
        self._arag_router = arag_router
        self._last_publish_at: float | None = None
        self._last_erm_metadata: dict[uuid.UUID, dict[str, object]] = {}

    async def run(self, message_id) -> None:
        started_at = perf_counter()
        wide_event: dict[str, object] = {
            "event": "message_pipeline_run",
            "message_id": str(message_id),
        }

        async with self._session_factory() as session:
            self._last_erm_metadata = {}
            assistant_message = await session.scalar(
                select(Message)
                .options(selectinload(Message.thread))
                .where(Message.id == message_id)
            )
            if assistant_message is None or assistant_message.role != "assistant":
                raise NonRetryablePipelineError(
                    f"Assistant message not found: {message_id}"
                )
            if assistant_message.reply_to_message_id is None:
                raise NonRetryablePipelineError(
                    f"Assistant message missing user turn: {assistant_message.id}"
                )

            user_message = await session.get(
                Message, assistant_message.reply_to_message_id
            )
            thread = await session.get(Thread, assistant_message.thread_id)
            if user_message is None or thread is None:
                raise NonRetryablePipelineError(
                    f"Thread context not found for message: {message_id}"
                )
            assistant_message_id = assistant_message.id
            assistant_message_id_str = str(assistant_message_id)
            thread_id_str = str(thread.id)

            context = await self._build_conversation_context(
                session, thread, user_message
            )
            effective_query_text = context["effective_query_text"]
            context_prefix = context["context_prefix"]
            conversation_history = context["conversation_history"]

            assistant_message.status = "running"
            await session.commit()

            try:
                route = "simple"
                sub_queries: list[str] = []
                if self._arag_router is not None:
                    result = await self._arag_router.classify(effective_query_text)
                    route = result.route
                    sub_queries = result.sub_queries

                assistant_message.selected_route = route
                assistant_message.sub_queries = sub_queries
                await session.commit()

                reasoning_trace: list[dict[str, object]] = []

                await self._publish(
                    assistant_message_id,
                    "route_selected",
                    {"route": route, "sub_queries": sub_queries},
                )

                wide_event["route"] = route
                wide_event["sub_queries"] = sub_queries
                wide_event["thread_id"] = thread_id_str

                if route == "multi_hop":
                    done_payload = await self._run_multi_hop_route(
                        session,
                        assistant_message,
                        effective_query_text,
                        context_prefix,
                        sub_queries,
                        wide_event,
                        reasoning_trace,
                    )
                elif route == "comparison":
                    done_payload = await self._run_comparison_route(
                        session,
                        assistant_message,
                        effective_query_text,
                        context_prefix,
                        sub_queries,
                        wide_event,
                        reasoning_trace,
                    )
                elif route == "aggregation":
                    done_payload = await self._run_aggregation_route(
                        session,
                        assistant_message,
                        effective_query_text,
                        context_prefix,
                        sub_queries,
                        wide_event,
                        reasoning_trace,
                    )
                elif route == "conversation":
                    done_payload = await self._run_conversation_route(
                        session,
                        assistant_message,
                        user_message.content_text,
                        conversation_history,
                        thread.summary,
                        wide_event,
                        reasoning_trace,
                    )
                else:
                    done_payload = await self._run_simple_route(
                        session,
                        assistant_message,
                        effective_query_text,
                        context_prefix,
                        wide_event,
                        reasoning_trace,
                    )

                if done_payload is None and self._llm_client is not None:
                    if wide_event.get("retrieval_count") == 0:
                        raise NoRelevantEvidenceError(
                            "No relevant evidence was found in your documents. "
                            "Upload a relevant document or try a different question."
                        )
                    raise AnswerGenerationError(
                        "The answer model returned no usable answer. Please retry."
                    )

                wide_event["outcome"] = "success"
            except Exception as exc:
                await self._mark_message_failed(
                    session,
                    assistant_message_id,
                    str(exc),
                )
                await self._publish(
                    assistant_message_id,
                    "done",
                    {
                        "thread_id": thread_id_str,
                        "message_id": assistant_message_id_str,
                        "content_parts": [],
                        "error": True,
                        "error_message": str(exc),
                    },
                )
                wide_event["outcome"] = "error"
                wide_event["error_type"] = type(exc).__name__
                wide_event["error_message"] = str(exc)
                raise
            finally:
                wide_event["duration_ms"] = round(
                    (perf_counter() - started_at) * 1000, 2
                )
                enrich_wide_event(pipeline=wide_event)

            assistant_message.status = "completed"
            assistant_message.completed_at = assistant_message.updated_at = (
                datetime.now(timezone.utc)
            )
            await session.commit()

            if done_payload:
                cp = answer_content_parts(
                    cast(str, done_payload["full_text"]),
                    cast(list[dict[str, object]], done_payload["evidence"]),
                )
                await self._publish(
                    assistant_message_id,
                    "done",
                    {
                        "thread_id": thread_id_str,
                        "message_id": assistant_message_id_str,
                        "content_parts": cp,
                        "reasoning_trace": done_payload["reasoning_trace"],
                        "segments": done_payload["segments"],
                        "evidence": done_payload["evidence"],
                        "context_usage": done_payload["context_usage"],
                        "full_text": done_payload["full_text"],
                        "id": done_payload["id"],
                        "error": False,
                    },
                )
                await self._update_thread_summary(
                    session,
                    thread,
                    user_message.content_text,
                    cast(str, done_payload["full_text"]),
                )
            else:
                await self._publish(
                    assistant_message_id,
                    "done",
                    {
                        "thread_id": thread_id_str,
                        "message_id": assistant_message_id_str,
                        "content_parts": [],
                        "error": False,
                    },
                )

    async def _mark_message_failed(
        self,
        session,
        message_id: uuid.UUID,
        error_message: str,
    ) -> None:
        await session.rollback()

        failed_message = await session.get(Message, message_id)
        if failed_message is None:
            return

        failed_message.status = "failed"
        failed_message.error_message = error_message
        failed_message.updated_at = datetime.now(timezone.utc)

        try:
            await session.commit()
        except SQLAlchemyError:
            await session.rollback()
            record_degradation(
                "message_failure_persistence",
                message_id=str(message_id),
                outcome="error",
            )

    async def _build_conversation_context(
        self,
        session,
        thread: Thread,
        user_message: Message,
    ) -> ConversationContext:
        messages = (
            await session.execute(
                select(Message)
                .options(selectinload(Message.answer))
                .where(
                    Message.thread_id == thread.id,
                    Message.position <= user_message.position,
                )
                .order_by(Message.position)
            )
        ).scalars()
        prior_messages = [
            message for message in messages if message.id != user_message.id
        ]

        transcript_lines: list[str] = []
        for message in prior_messages:
            if message.role == "assistant":
                content = (
                    message.answer.full_text
                    if message.answer is not None
                    else message.content_text
                )
            else:
                content = message.content_text
            if not content.strip():
                continue
            transcript_lines.append(f"{message.role.title()}: {content.strip()}")

        recent_lines = transcript_lines[-6:]
        context_prefix = ""
        if thread.summary.strip():
            context_prefix += f"Prior thread summary:\n{thread.summary.strip()}\n\n"
        if recent_lines:
            context_prefix += (
                "Recent conversation:\n" + "\n".join(recent_lines) + "\n\n"
            )

        effective_query_text = user_message.content_text
        if context_prefix and self._llm_client is not None:
            try:
                rewritten = await self._llm_client.generate(
                    [
                        {
                            "role": "system",
                            "content": (
                                "Rewrite the user's latest message into a standalone "
                                "retrieval query using the conversation context. Return "
                                "plain text only."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"{context_prefix}Latest user message:\n"
                                f"{user_message.content_text}"
                            ),
                        },
                    ]
                )
                effective_query_text = rewritten.strip() or user_message.content_text
            except Exception:
                effective_query_text = user_message.content_text

        return {
            "conversation_history": "\n".join(transcript_lines).strip() or None,
            "context_prefix": context_prefix.strip() or None,
            "effective_query_text": effective_query_text,
        }

    async def _update_thread_summary(
        self,
        session,
        thread: Thread,
        user_text: str,
        answer_text: str,
    ) -> None:
        if self._llm_client is None:
            thread.summary = (
                thread.summary + f"\nUser: {user_text}\nAssistant: {answer_text}"
            ).strip()[:2000]
            await session.commit()
            return

        messages = [
            {
                "role": "system",
                "content": (
                    "Update the conversation summary for a chat thread. Keep the "
                    "summary concise, factual, and useful for follow-up retrieval. "
                    "Return plain text only."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Existing summary:\n{thread.summary or '(none)'}\n\n"
                    f"New user message:\n{user_text}\n\n"
                    f"New assistant answer:\n{answer_text}"
                ),
            },
        ]
        try:
            summary = (await self._llm_client.generate(messages)).strip()
        except Exception:
            summary = (
                thread.summary + f"\nUser: {user_text}\nAssistant: {answer_text}"
            ).strip()
        thread.summary = summary[:4000]
        await session.commit()

    async def _run_simple_route(
        self,
        session,
        message: Message,
        query_text: str,
        context_prefix: str | None = None,
        wide_event: dict[str, object] | None = None,
        reasoning_trace: list[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        await self._publish(
            message.id,
            "content_parts",
            {"parts": [reasoning_part("Routing Query via Simple Route...")]},
        )
        self._trace_step(reasoning_trace, "Routing Query via Simple Route...")

        if self._embedding_client is None or self._qdrant_store is None:
            return None

        dense_vector = (await self._embedding_client.embed_texts_async([query_text]))[0]
        search_results = await self._qdrant_store.hybrid_search(
            query_text=query_text,
            dense_vector=dense_vector,
            dense_limit=20,
            sparse_limit=20,
            fused_limit=20,
        )
        if isinstance(search_results, dict):
            search_results = {
                stage: await self._filter_retrievable_points(session, points)
                for stage, points in search_results.items()
            }
        else:
            search_results = await self._filter_retrievable_points(
                session, search_results
            )
        await self._publish(
            message.id,
            "content_parts",
            {"parts": [reasoning_part("Retrieving Evidence from Qdrant...")]},
        )
        self._trace_step(reasoning_trace, "Retrieving Evidence from Qdrant...")
        await self._stage_candidates(session, message, search_results)

        fused_points = (
            search_results.get("fused", [])
            if isinstance(search_results, dict)
            else search_results
        )
        if wide_event is not None:
            wide_event["retrieval_count"] = len(fused_points)

        trace_evidence_ids = [
            uuid.UUID(point.payload["evidence_id"]) for point in fused_points[:5]
        ]
        if trace_evidence_ids and reasoning_trace is not None:
            trace_rows = (
                await session.scalars(
                    select(Evidence)
                    .where(Evidence.id.in_(trace_evidence_ids))
                    .options(selectinload(Evidence.document))
                )
            ).all()
            trace_by_id = {row.id: row for row in trace_rows}
            trace_candidates = [
                candidate
                for evidence_id in trace_evidence_ids
                if evidence_id in trace_by_id
                for candidate in _candidate_rows(trace_by_id, [evidence_id])
            ]
            self._trace_retrieval(
                reasoning_trace,
                f"Retrieved {len(trace_candidates)} candidates",
                trace_candidates,
            )

        await self._publish(
            message.id,
            "content_parts",
            {"parts": [reasoning_part("Fusing dense + sparse candidates via RRF...")]},
        )
        self._trace_step(reasoning_trace, "Fusing dense + sparse candidates via RRF...")

        selected_evidence_ids = [
            uuid.UUID(point.payload["evidence_id"]) for point in fused_points
        ]
        if self._rerank_client is not None and fused_points:
            await self._publish(
                message.id,
                "content_parts",
                {
                    "parts": [
                        reasoning_part("Reranking top-20 candidates via Cohere...")
                    ]
                },
            )
            self._trace_step(
                reasoning_trace, "Reranking top-20 candidates via Cohere..."
            )
            selected_evidence_ids = await self._rerank_fused_candidates(
                session, message, query_text, dense_vector, fused_points
            )

        if wide_event is not None:
            wide_event["rerank_count"] = len(selected_evidence_ids)

        if self._llm_client is not None and selected_evidence_ids:
            return await self._generate_and_persist_answer(
                session,
                message,
                query_text,
                selected_evidence_ids,
                SIMPLE_SYSTEM_PROMPT,
                context_prefix=context_prefix,
                evidence_metadata=getattr(self, "_last_erm_metadata", None),
                reasoning_trace=reasoning_trace,
            )

        return None

    async def _retrieve_evidence(
        self,
        session,
        query_text: str,
        rerank_query: str | None = None,
        top_n: int = 5,
        rerank: bool = True,
    ) -> tuple[
        list[uuid.UUID], list[dict[str, object]], dict[uuid.UUID, dict[str, object]]
    ]:
        if self._embedding_client is None or self._qdrant_store is None:
            return [], [], {}

        dense_vector = (await self._embedding_client.embed_texts_async([query_text]))[0]
        search_results = await self._qdrant_store.hybrid_search(
            query_text=query_text,
            dense_vector=dense_vector,
            dense_limit=20,
            sparse_limit=20,
            fused_limit=20,
        )
        fused_points = (
            search_results.get("fused", [])
            if isinstance(search_results, dict)
            else search_results
        )
        fused_points = await self._filter_retrievable_points(session, fused_points)
        if not fused_points:
            return [], [], {}

        rerank_q = rerank_query or query_text
        documents: list[str] = []
        evidence_ids: list[uuid.UUID] = []
        candidates: list[dict[str, object]] = []
        for point in fused_points:
            evidence_id = uuid.UUID(point.payload["evidence_id"])
            evidence = await session.scalar(
                select(Evidence)
                .where(Evidence.id == evidence_id)
                .options(selectinload(Evidence.document))
            )
            if evidence is None:
                continue
            documents.append(evidence.content)
            evidence_ids.append(evidence_id)
            candidates.append(
                {
                    "evidence_id": str(evidence_id),
                    "document_title": evidence.document.title,
                    "page": evidence.page,
                    "snippet": evidence.content[:160],
                }
            )

        if self._rerank_client is not None and rerank:
            try:
                results = await self._rerank_client.rerank(
                    query=rerank_q,
                    documents=documents,
                    top_n=top_n,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                    raise
                record_degradation(
                    "rerank",
                    reason="upstream_status",
                    status_code=exc.response.status_code,
                    candidate_count=len(documents),
                )
                return evidence_ids[:top_n], candidates[:top_n], {}
            ranked = await self._apply_erm_to_ranked_results(
                session,
                query_embedding=dense_vector,
                evidence_ids=evidence_ids,
                results=results,
            )
            selected = [item["evidence_id"] for item in ranked[:top_n]]
            selected_candidates = [candidates[item["index"]] for item in ranked[:top_n]]
            evidence_metadata = {
                item["evidence_id"]: item["metadata"]
                for item in ranked[:top_n]
                if item["metadata"]
            }
            return selected, selected_candidates, evidence_metadata

        return evidence_ids[:top_n], candidates[:top_n], {}

    async def _retrieve_evidence_isolated(
        self,
        query_text: str,
        *,
        rerank_query: str | None = None,
        top_n: int = 5,
        rerank: bool = True,
    ) -> tuple[
        list[uuid.UUID], list[dict[str, object]], dict[uuid.UUID, dict[str, object]]
    ]:
        async with self._session_factory() as retrieval_session:
            return await self._retrieve_evidence(
                retrieval_session,
                query_text,
                rerank_query=rerank_query,
                top_n=top_n,
                rerank=rerank,
            )

    async def _rerank_evidence_ids(
        self,
        session,
        query_text: str,
        evidence_ids: list[uuid.UUID],
        top_n: int,
    ) -> tuple[
        list[uuid.UUID], list[dict[str, object]], dict[uuid.UUID, dict[str, object]]
    ]:
        if self._rerank_client is None:
            return evidence_ids[:top_n], [], {}

        rows = await session.scalars(
            select(Evidence)
            .where(Evidence.id.in_(evidence_ids))
            .options(selectinload(Evidence.document))
        )
        by_id = {row.id: row for row in rows}
        ordered_ids = [
            evidence_id for evidence_id in evidence_ids if evidence_id in by_id
        ]
        documents = [by_id[evidence_id].content for evidence_id in ordered_ids]
        try:
            results = await self._rerank_client.rerank(
                query=query_text,
                documents=documents,
                top_n=top_n,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                raise
            record_degradation(
                "rerank",
                reason="upstream_status",
                status_code=exc.response.status_code,
                candidate_count=len(documents),
            )
            selected_ids = ordered_ids[:top_n]
            return selected_ids, _candidate_rows(by_id, selected_ids), {}

        ranked = await self._apply_erm_to_ranked_results(
            session,
            query_embedding=(
                await self._embedding_client.embed_texts_async([query_text])
            )[0]
            if self._embedding_client is not None
            else [],
            evidence_ids=ordered_ids,
            results=results,
        )
        selected_ids = [item["evidence_id"] for item in ranked[:top_n]]
        metadata = {
            item["evidence_id"]: item["metadata"]
            for item in ranked[:top_n]
            if item["metadata"]
        }
        return selected_ids, _candidate_rows(by_id, selected_ids), metadata

    async def _run_multi_hop_route(
        self,
        session,
        message: Message,
        query_text: str,
        context_prefix: str | None,
        sub_queries: list[str],
        wide_event: dict[str, object] | None = None,
        reasoning_trace: list[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        if not sub_queries:
            sub_queries = [query_text]
        sub_queries = sub_queries[:MAX_SUB_QUERIES]

        all_evidence_ids: list[uuid.UUID] = []
        intermediate_answers: list[str] = []
        evidence_metadata_by_id: dict[uuid.UUID, dict[str, object]] = {}

        for i, sub_query in enumerate(sub_queries):
            step_text = (
                f"Multi-hop step {i + 1}/{len(sub_queries)}: "
                f"Retrieving for '{sub_query}'..."
            )
            await self._publish(
                message.id,
                "content_parts",
                {"parts": [reasoning_part(step_text)]},
            )
            self._trace_step(reasoning_trace, step_text)

            evidence_ids, candidates, metadata = await self._retrieve_evidence(
                session, sub_query
            )
            all_evidence_ids.extend(evidence_ids)
            evidence_metadata_by_id.update(metadata)
            self._trace_retrieval(
                reasoning_trace, f"Retrieved {len(candidates)} candidates", candidates
            )

            intermediate = ""
            if evidence_ids and self._llm_client is not None:
                evidence_contents: list[str] = []
                for eid in evidence_ids:
                    evidence = await session.get(Evidence, eid)
                    if evidence is not None:
                        evidence_contents.append(evidence.content)
                context = context_prefix + "\n\n" if context_prefix else ""
                if intermediate_answers:
                    context += (
                        "Previous steps:\n"
                        + "\n".join(
                            f"Step {j + 1}: {ans}"
                            for j, ans in enumerate(intermediate_answers)
                        )
                        + "\n\n"
                    )
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Answer the current sub-question concisely using the provided evidence. "
                            "If the evidence does not contain the answer, say so."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"{context}"
                            f"Sub-question: {sub_query}\n"
                            "Evidence:\n" + "\n".join(evidence_contents)
                        ),
                    },
                ]
                raw = await self._llm_client.generate(messages)
                intermediate = raw.strip()

            intermediate_answers.append(intermediate)

            hop_payload = {
                "hop": i + 1,
                "sub_query": sub_query,
                "intermediate_answer": intermediate,
            }
            await self._publish(message.id, "hop_progress", hop_payload)
            self._trace_hop(reasoning_trace, hop_payload)

        seen: set[uuid.UUID] = set()
        unique_evidence: list[uuid.UUID] = []
        for eid in all_evidence_ids:
            if eid not in seen:
                seen.add(eid)
                unique_evidence.append(eid)

        if wide_event is not None:
            wide_event["multi_hop_steps"] = len(sub_queries)
            wide_event["retrieved_evidence_count"] = len(unique_evidence)

        chain_context = "Chain of reasoning:\n" + "\n".join(
            f"Step {i + 1}: {ans}" for i, ans in enumerate(intermediate_answers)
        )

        if self._llm_client is not None and unique_evidence:
            return await self._generate_and_persist_answer(
                session,
                message,
                query_text,
                unique_evidence,
                MULTI_HOP_SYSTEM_PROMPT,
                context_prefix="\n\n".join(
                    part for part in (context_prefix, chain_context) if part
                ),
                evidence_metadata=evidence_metadata_by_id,
                reasoning_trace=reasoning_trace,
            )

        return None

    async def _run_comparison_route(
        self,
        session,
        message: Message,
        query_text: str,
        context_prefix: str | None,
        sub_queries: list[str],
        wide_event: dict[str, object] | None = None,
        reasoning_trace: list[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        if not sub_queries:
            sub_queries = [query_text]
        sub_queries = sub_queries[:MAX_SUB_QUERIES]

        step_text = (
            f"Comparison: Retrieving evidence for {len(sub_queries)} entities..."
        )
        await self._publish(
            message.id,
            "content_parts",
            {"parts": [reasoning_part(step_text)]},
        )
        self._trace_step(reasoning_trace, step_text)

        import asyncio

        tasks = [
            self._retrieve_evidence_isolated(
                sq,
                rerank_query=query_text,
                top_n=20,
                rerank=False,
            )
            for sq in sub_queries
        ]
        results = await asyncio.gather(*tasks)

        seen: set[uuid.UUID] = set()
        all_evidence_ids: list[uuid.UUID] = []
        evidence_metadata_by_id: dict[uuid.UUID, dict[str, object]] = {}
        for sq, (ev_ids, cands, metadata) in zip(sub_queries, results, strict=True):
            self._trace_retrieval(
                reasoning_trace,
                f"Retrieved candidates for '{sq}'",
                cands,
            )
            evidence_metadata_by_id.update(metadata)
            for eid in ev_ids:
                if eid not in seen:
                    seen.add(eid)
                    all_evidence_ids.append(eid)

        if self._rerank_client is not None and all_evidence_ids:
            await self._publish(
                message.id,
                "content_parts",
                {"parts": [reasoning_part("Ranking merged evidence...")]},
            )
            self._trace_step(reasoning_trace, "Ranking merged evidence...")
            (
                all_evidence_ids,
                merged_candidates,
                evidence_metadata_by_id,
            ) = await self._rerank_evidence_ids(
                session, query_text, all_evidence_ids, top_n=10
            )
            self._trace_retrieval(
                reasoning_trace, "Reranked merged candidates", merged_candidates
            )

        if wide_event is not None:
            wide_event["comparison_entities"] = len(sub_queries)
            wide_event["retrieved_evidence_count"] = len(all_evidence_ids)

        if self._llm_client is not None and all_evidence_ids:
            return await self._generate_and_persist_answer(
                session,
                message,
                query_text,
                all_evidence_ids,
                COMPARISON_SYSTEM_PROMPT,
                context_prefix=context_prefix,
                evidence_metadata=evidence_metadata_by_id,
                reasoning_trace=reasoning_trace,
            )

        return None

    async def _run_aggregation_route(
        self,
        session,
        message: Message,
        query_text: str,
        context_prefix: str | None,
        sub_queries: list[str],
        wide_event: dict[str, object] | None = None,
        reasoning_trace: list[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        if not sub_queries:
            sub_queries = [query_text]
        sub_queries = sub_queries[:MAX_SUB_QUERIES]

        step_text = (
            f"Aggregation: Retrieving across {len(sub_queries)} reformulations..."
        )
        await self._publish(
            message.id,
            "content_parts",
            {"parts": [reasoning_part(step_text)]},
        )
        self._trace_step(reasoning_trace, step_text)

        import asyncio

        tasks = [
            self._retrieve_evidence_isolated(sq, top_n=20, rerank=False)
            for sq in sub_queries
        ]
        results = await asyncio.gather(*tasks)

        seen: set[uuid.UUID] = set()
        all_evidence_ids: list[uuid.UUID] = []
        evidence_metadata_by_id: dict[uuid.UUID, dict[str, object]] = {}
        for sq, (ev_ids, cands, metadata) in zip(sub_queries, results, strict=True):
            self._trace_retrieval(
                reasoning_trace,
                f"Retrieved candidates for '{sq}'",
                cands,
            )
            evidence_metadata_by_id.update(metadata)
            for eid in ev_ids:
                if eid not in seen:
                    seen.add(eid)
                    all_evidence_ids.append(eid)

        if self._rerank_client is not None and all_evidence_ids:
            await self._publish(
                message.id,
                "content_parts",
                {"parts": [reasoning_part("Ranking merged evidence...")]},
            )
            self._trace_step(reasoning_trace, "Ranking merged evidence...")
            (
                all_evidence_ids,
                merged_candidates,
                evidence_metadata_by_id,
            ) = await self._rerank_evidence_ids(
                session, query_text, all_evidence_ids, top_n=10
            )
            self._trace_retrieval(
                reasoning_trace, "Reranked merged candidates", merged_candidates
            )

        if wide_event is not None:
            wide_event["aggregation_reformulations"] = len(sub_queries)
            wide_event["retrieved_evidence_count"] = len(all_evidence_ids)

        if self._llm_client is not None and all_evidence_ids:
            return await self._generate_and_persist_answer(
                session,
                message,
                query_text,
                all_evidence_ids,
                AGGREGATION_SYSTEM_PROMPT,
                context_prefix=context_prefix,
                evidence_metadata=evidence_metadata_by_id,
                reasoning_trace=reasoning_trace,
            )

        return None

    async def _run_conversation_route(
        self,
        session,
        message: Message,
        user_text: str,
        conversation_history: str | None,
        thread_summary: str | None,
        wide_event: dict[str, object] | None = None,
        reasoning_trace: list[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        await self._publish(
            message.id,
            "content_parts",
            {"parts": [reasoning_part("Reading prior turns from thread memory...")]},
        )
        self._trace_step(reasoning_trace, "Reading prior turns from thread memory...")

        context_blocks: list[str] = []
        if thread_summary and thread_summary.strip():
            context_blocks.append(f"Thread summary:\n{thread_summary.strip()}")
        if conversation_history and conversation_history.strip():
            context_blocks.append(
                "Conversation history before the latest user message:\n"
                f"{conversation_history.strip()}"
            )
        if not context_blocks:
            context_blocks.append(
                "Conversation history before the latest user message:\n(none)"
            )

        if wide_event is not None:
            wide_event["conversation_history_present"] = bool(
                conversation_history and conversation_history.strip()
            )

        return await self._generate_and_persist_context_answer(
            session,
            message,
            user_text,
            "\n\n".join(context_blocks),
            CONVERSATION_SYSTEM_PROMPT,
            reasoning_trace=reasoning_trace,
        )

    async def _stage_candidates(
        self, session, message: Message, search_results
    ) -> None:
        if isinstance(search_results, dict):
            stages = search_results.items()
        else:
            stages = (("fused", search_results),)

        for stage, points in stages:
            for rank, point in enumerate(points):
                session.add(
                    MessageEvidenceCandidate(
                        message_id=message.id,
                        stage=stage,
                        evidence_id=uuid.UUID(point.payload["evidence_id"]),
                        rank=rank,
                        score=point.score,
                    )
                )

    async def _filter_retrievable_points(self, session, points):
        point_ids: list[uuid.UUID] = []
        evidence_ids_by_point: dict[int, uuid.UUID] = {}
        for point in points:
            try:
                evidence_id = uuid.UUID(str(point.payload["evidence_id"]))
            except (KeyError, TypeError, ValueError):
                continue
            point_ids.append(evidence_id)
            evidence_ids_by_point[id(point)] = evidence_id
        if not point_ids:
            return []

        result = await session.execute(
            select(Evidence.id)
            .join(Document, Document.id == Evidence.document_id)
            .join(Source, Source.id == Document.source_id)
            .where(
                Evidence.id.in_(point_ids),
                Document.is_current.is_(True),
                Document.status.in_(("ready", "ready_with_warnings")),
                Source.deleted_at.is_(None),
            )
        )
        allowed_ids = set(result.scalars())
        return [
            point
            for point in points
            if evidence_ids_by_point.get(id(point)) in allowed_ids
        ]

    async def _rerank_fused_candidates(
        self,
        session,
        message: Message,
        query_text: str,
        query_embedding: list[float],
        fused_points,
    ) -> list[uuid.UUID]:
        if self._rerank_client is None:
            return []

        documents: list[str] = []
        evidence_ids: list[uuid.UUID] = []

        for point in fused_points:
            evidence_id = uuid.UUID(point.payload["evidence_id"])
            evidence = await session.get(Evidence, evidence_id)
            documents.append(evidence.content)
            evidence_ids.append(evidence_id)

        try:
            results = await self._rerank_client.rerank(
                query=query_text,
                documents=documents,
                top_n=5,
            )
        except httpx.TimeoutException as exc:
            record_degradation(
                "rerank",
                reason="timeout",
                error_type=type(exc).__name__,
                candidate_count=len(documents),
            )
            return evidence_ids[:5]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                raise
            record_degradation(
                "rerank",
                reason="upstream_status",
                status_code=exc.response.status_code,
                candidate_count=len(documents),
            )
            return evidence_ids[:5]

        ranked = await self._apply_erm_to_ranked_results(
            session,
            query_embedding=query_embedding,
            evidence_ids=evidence_ids,
            results=results,
        )

        selected_evidence_ids: list[uuid.UUID] = []
        self._last_erm_metadata = {
            item["evidence_id"]: item["metadata"] for item in ranked if item["metadata"]
        }

        for stage in ("reranked", "selected"):
            for rank, item in enumerate(ranked):
                evidence_id = item["evidence_id"]
                session.add(
                    MessageEvidenceCandidate(
                        message_id=message.id,
                        stage=stage,
                        evidence_id=evidence_id,
                        rank=rank,
                        score=item["score"],
                        extra=item["metadata"] or {},
                    )
                )
                if stage == "selected":
                    selected_evidence_ids.append(evidence_id)

        return selected_evidence_ids

    async def _generate_and_persist_answer(
        self,
        session,
        message: Message,
        query_text: str,
        selected_evidence_ids: list[uuid.UUID],
        system_prompt: str | None = None,
        context_prefix: str | None = None,
        evidence_metadata: dict[uuid.UUID, dict[str, object]] | None = None,
        reasoning_trace: list[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        if self._llm_client is None:
            return None

        parser = JsonStreamParser()
        evidence_contents: list[str] = []
        evidence_payloads: list[dict[str, object]] = []
        for evidence_id in selected_evidence_ids:
            evidence = await session.get(Evidence, evidence_id)
            evidence_contents.append(evidence.content)
            asset_key = (evidence.extra or {}).get("asset_key")
            evidence_payloads.append(
                {
                    "id": str(evidence_id),
                    "content": evidence.content,
                    "kind": (evidence.extra or {}).get("kind", "text"),
                    "asset_key": asset_key,
                    "asset_url": (
                        f"/api/v1/documents/{evidence.document_id}/assets/"
                        f"{str(asset_key).rsplit('/', 1)[-1]}"
                        if asset_key
                        else None
                    ),
                    **(evidence_metadata or {}).get(evidence_id, {}),
                }
            )

        prompt = system_prompt or SIMPLE_SYSTEM_PROMPT

        user_content = f"Question: {query_text}\n"
        if context_prefix:
            user_content += f"{context_prefix}\n\n"
        user_content += "Evidence:\n" + "\n\n".join(
            f"[ID: {ev['id']}] {ev['content']}" for ev in evidence_payloads
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]

        usage_messages = messages
        usage_completion = ""
        async for chunk in self._llm_client.generate_stream(messages):
            usage_completion += chunk
            parser.feed(chunk)
            accumulated = parser.get_accumulated_text()
            await self._publish(
                message.id,
                "content_parts",
                {
                    "parts": [
                        reasoning_part("Generating Answer..."),
                        text_part(accumulated),
                    ]
                },
                throttle=False,
            )
        self._trace_step(reasoning_trace, "Generating Answer...")

        parsed = parser.parse_final()
        if not parsed:
            retry_prompt = (
                prompt
                + " Previous output could not be parsed. Return ONLY a valid JSON "
                + "array of objects with exactly the keys text and evidence_ids."
            )
            retry_parser = JsonStreamParser()
            await self._publish(
                message.id,
                "content_parts",
                {"parts": [reasoning_part("Formatting the answer...")]},
                throttle=False,
            )
            retry_messages = [
                {"role": "system", "content": retry_prompt},
                {"role": "user", "content": user_content},
            ]
            usage_messages = retry_messages
            usage_completion = ""
            async for chunk in self._llm_client.generate_stream(retry_messages):
                usage_completion += chunk
                retry_parser.feed(chunk)
                await self._publish(
                    message.id,
                    "content_parts",
                    {
                        "parts": [
                            reasoning_part("Formatting the answer..."),
                            text_part(retry_parser.get_accumulated_text()),
                        ]
                    },
                    throttle=False,
                )
            parsed = retry_parser.parse_final()
            if not parsed:
                raise AnswerGenerationError(
                    "The answer model returned unusable structured output. Please retry."
                )
        return self._persist_segments(
            session,
            message,
            parsed,
            evidence_payloads,
            reasoning_trace,
            self._context_manager.measure(
                usage_messages,
                usage_completion,
            ).as_dict(),
        )

    async def _generate_and_persist_context_answer(
        self,
        session,
        message: Message,
        question_text: str,
        context_text: str,
        system_prompt: str,
        reasoning_trace: list[dict[str, object]] | None = None,
    ) -> dict[str, object] | None:
        if self._llm_client is None:
            return None

        parser = JsonStreamParser()
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Question: {question_text}\n\n{context_text}",
            },
        ]

        usage_completion = ""
        async for chunk in self._llm_client.generate_stream(messages):
            usage_completion += chunk
            parser.feed(chunk)
            accumulated = parser.get_accumulated_text()
            await self._publish(
                message.id,
                "content_parts",
                {
                    "parts": [
                        reasoning_part("Generating Answer from thread memory..."),
                        text_part(accumulated),
                    ]
                },
                throttle=False,
            )
        self._trace_step(reasoning_trace, "Generating Answer from thread memory...")

        parsed = parser.parse_final()
        if not parsed:
            return None
        return self._persist_segments(
            session,
            message,
            parsed,
            [],
            reasoning_trace,
            self._context_manager.measure(
                messages,
                usage_completion,
            ).as_dict(),
        )

    def _trace_step(
        self,
        reasoning_trace: list[dict[str, object]] | None,
        text: str,
    ) -> None:
        if reasoning_trace is None:
            return
        reasoning_trace.append({"type": "step", "text": text})

    def _trace_hop(
        self,
        reasoning_trace: list[dict[str, object]] | None,
        hop: dict[str, object],
    ) -> None:
        if reasoning_trace is None:
            return
        reasoning_trace.append(
            {
                "type": "hop",
                "hop": hop.get("hop"),
                "sub_query": hop.get("sub_query"),
                "intermediate_answer": hop.get("intermediate_answer"),
            }
        )

    def _trace_retrieval(
        self,
        reasoning_trace: list[dict[str, object]] | None,
        label: str,
        candidates: list[dict[str, object]],
    ) -> None:
        if reasoning_trace is None:
            return
        reasoning_trace.append(
            {
                "type": "retrieval",
                "label": label,
                "candidates": candidates,
            }
        )

    async def _apply_erm_to_ranked_results(
        self,
        session,
        *,
        query_embedding: list[float],
        evidence_ids: list[uuid.UUID],
        results,
    ) -> list[RankedEvidenceResult]:
        adjustments = await load_erm_adjustments(
            session,
            query_embedding=query_embedding,
            evidence_ids=evidence_ids,
        )

        ranked: list[RankedEvidenceResult] = []
        for result in results:
            evidence_id = evidence_ids[result.index]
            adjustment = adjustments.get(evidence_id)
            multiplier = adjustment.multiplier if adjustment is not None else 1.0
            base_score = result.relevance_score
            ranked.append(
                {
                    "evidence_id": evidence_id,
                    "index": result.index,
                    "metadata": self._erm_metadata(adjustment),
                    "score": base_score * multiplier,
                }
            )

        ranked.sort(key=lambda item: cast(float, item["score"]), reverse=True)
        return ranked

    def _erm_metadata(
        self, adjustment: ErmAdjustment | None
    ) -> dict[str, object] | None:
        if adjustment is None or adjustment.state is None:
            return None
        return {
            "erm_multiplier": adjustment.multiplier,
            "erm_state": adjustment.state,
        }

    def _persist_segments(
        self,
        session,
        message: Message,
        parsed_segments: list[dict[str, object]],
        evidence_payloads: list[dict[str, object]],
        reasoning_trace: list[dict[str, object]] | None = None,
        context_usage: dict[str, object] | None = None,
    ) -> dict[str, object]:
        valid_ids = {ev["id"] for ev in evidence_payloads}

        def _resolve_citation(raw: object) -> str | None:
            raw_str = str(raw).strip()
            for prefix in ("[ID: ", "id: ", "ID: ", "id=", "ID="):
                if raw_str.startswith(prefix):
                    raw_str = raw_str.removeprefix(prefix).removesuffix("]")
                    break
            try:
                parsed = uuid.UUID(raw_str)
                if str(parsed) in valid_ids:
                    return str(parsed)
            except (ValueError, AttributeError):
                pass
            return None

        full_text_parts = [str(item["text"]) for item in parsed_segments]
        answer = Answer(
            id=uuid.uuid4(),
            message_id=message.id,
            full_text=join_segment_texts(full_text_parts),
            reasoning_trace=list(reasoning_trace) if reasoning_trace else [],
        )
        session.add(answer)

        segment_payloads: list[dict[str, object]] = []

        for segment_index, item in enumerate(parsed_segments):
            text = str(item["text"])
            raw_evidence_ids = item.get("evidence_ids", [])
            if not isinstance(raw_evidence_ids, list):
                raise ValueError("evidence_ids must be a list")

            resolved: list[str] = []
            for raw in raw_evidence_ids:
                citation = _resolve_citation(raw)
                if citation:
                    resolved.append(citation)

            segment_id = uuid.uuid4()
            session.add(
                Segment(
                    id=segment_id,
                    answer_id=answer.id,
                    segment_index=segment_index,
                    text=text,
                    evidence_ids=resolved,
                )
            )

            segment_payloads.append(
                {
                    "id": str(segment_id),
                    "segment_index": segment_index,
                    "text": text,
                    "evidence_ids": resolved,
                    "rating": None,
                }
            )
        answer.extra = {
            **(answer.extra or {}),
            "context_usage": context_usage or {},
            "retrieved_evidence_ids": [str(ev["id"]) for ev in evidence_payloads],
            "evidence_metadata": {
                str(ev["id"]): {
                    key: value
                    for key, value in ev.items()
                    if key in {"erm_multiplier", "erm_state"}
                }
                for ev in evidence_payloads
                if "erm_state" in ev or "erm_multiplier" in ev
            },
        }
        return {
            "id": str(answer.id),
            "message_id": str(message.id),
            "full_text": answer.full_text,
            "reasoning_trace": answer.reasoning_trace,
            "segments": segment_payloads,
            "evidence": evidence_payloads,
            "context_usage": context_usage or {},
        }

    async def _publish(
        self,
        message_id,
        event: str,
        data: Mapping[str, object],
        throttle: bool = True,
    ) -> None:
        if throttle:
            now = perf_counter()
            if self._last_publish_at is not None:
                elapsed = now - self._last_publish_at
                if elapsed < MIN_EVENT_INTERVAL_S:
                    await asyncio.sleep(MIN_EVENT_INTERVAL_S - elapsed)
            self._last_publish_at = perf_counter()

        channel = f"message:{message_id}:events"
        message = json.dumps({"event": event, "data": data})
        try:
            await self._redis.publish(channel, message)
        except Exception as exc:
            record_degradation(
                "message_event_publish",
                message_id=str(message_id),
                published_event=event,
                error_type=type(exc).__name__,
            )
