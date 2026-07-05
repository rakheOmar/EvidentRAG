from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from time import perf_counter

from app.application.query_pipeline.json_stream_parser import JsonStreamParser
from app.infrastructure.db.models import (
    Answer,
    Evidence,
    Query,
    QueryEvidenceCandidate,
    SentenceTrace,
    SentenceTraceEvidence,
)

logger = logging.getLogger(__name__)


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
    ) -> None:
        self._session_factory = session_factory
        self._redis = redis
        self._embedding_client = embedding_client
        self._qdrant_store = qdrant_store
        self._rerank_client = rerank_client
        self._llm_client = llm_client

    async def run(self, query_id) -> None:
        started_at = perf_counter()
        wide_event: dict[str, object] = {
            "event": "query_pipeline_run",
            "query_id": str(query_id),
            "route": "simple",
        }

        async with self._session_factory() as session:
            query = await session.get(Query, query_id)
            if query is None:
                raise ValueError(f"Query not found: {query_id}")

            query.status = "running"
            await session.commit()
            await self._publish(query.id, "route_selected", {"route": "simple"})

            try:
                done_payload = await self._run_simple_route(session, query, wide_event)
                wide_event["outcome"] = "success"
            except Exception as exc:
                query.status = "failed"
                query.error_message = str(exc)
                query.updated_at = datetime.now(timezone.utc)
                await session.commit()
                await self._publish(query.id, "error", {"message": str(exc)})
                wide_event["outcome"] = "error"
                wide_event["error_type"] = type(exc).__name__
                wide_event["error_message"] = str(exc)
                raise
            finally:
                wide_event["duration_ms"] = round(
                    (perf_counter() - started_at) * 1000, 2
                )
                logger.info("pipeline_run", extra={"wide_event": wide_event})

            query.status = "completed"
            query.completed_at = query.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await self._publish(
                query.id,
                "done",
                done_payload or {"status": "completed"},
            )

    async def _run_simple_route(
        self, session, query: Query, wide_event: dict[str, object] | None = None
    ) -> dict[str, object] | None:
        if self._embedding_client is None or self._qdrant_store is None:
            return None

        dense_vector = self._embedding_client.embed_texts([query.query_text])[0]
        search_results = await self._qdrant_store.hybrid_search(
            query_text=query.query_text,
            dense_vector=dense_vector,
            dense_limit=20,
            sparse_limit=20,
            fused_limit=20,
        )
        await self._publish(query.id, "retrieving", {"status": "retrieving"})
        await self._stage_candidates(session, query, search_results)

        fused_points = (
            search_results.get("fused", [])
            if isinstance(search_results, dict)
            else search_results
        )
        if wide_event is not None:
            wide_event["retrieval_count"] = len(fused_points)

        selected_evidence_ids = [
            uuid.UUID(point.payload["evidence_id"]) for point in fused_points
        ]
        if self._rerank_client is not None and fused_points:
            selected_evidence_ids = await self._rerank_fused_candidates(
                session, query, fused_points
            )

        if wide_event is not None:
            wide_event["rerank_count"] = len(selected_evidence_ids)

        if self._llm_client is not None and selected_evidence_ids:
            return await self._generate_and_persist_answer(
                session, query, selected_evidence_ids
            )

        return None

    async def _stage_candidates(self, session, query: Query, search_results) -> None:
        if isinstance(search_results, dict):
            stages = search_results.items()
        else:
            stages = (("fused", search_results),)

        for stage, points in stages:
            for rank, point in enumerate(points):
                session.add(
                    QueryEvidenceCandidate(
                        query_id=query.id,
                        stage=stage,
                        evidence_id=uuid.UUID(point.payload["evidence_id"]),
                        rank=rank,
                        score=point.score,
                    )
                )

    async def _rerank_fused_candidates(
        self, session, query: Query, fused_points
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

        results = await self._rerank_client.rerank(
            query=query.query_text,
            documents=documents,
            top_n=5,
        )

        selected_evidence_ids: list[uuid.UUID] = []

        for stage in ("reranked", "selected"):
            for rank, result in enumerate(results):
                evidence_id = evidence_ids[result.index]
                session.add(
                    QueryEvidenceCandidate(
                        query_id=query.id,
                        stage=stage,
                        evidence_id=evidence_id,
                        rank=rank,
                        score=result.relevance_score,
                    )
                )
                if stage == "selected":
                    selected_evidence_ids.append(evidence_id)

        return selected_evidence_ids

    async def _generate_and_persist_answer(
        self,
        session,
        query: Query,
        selected_evidence_ids: list[uuid.UUID],
    ) -> dict[str, object] | None:
        if self._llm_client is None:
            return None

        parser = JsonStreamParser()
        evidence_contents: list[str] = []
        evidence_payloads: list[dict[str, object]] = []
        for evidence_id in selected_evidence_ids:
            evidence = await session.get(Evidence, evidence_id)
            evidence_contents.append(evidence.content)
            evidence_payloads.append(
                {
                    "id": str(evidence_id),
                    "content": evidence.content,
                }
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "Answer the question using ONLY the provided evidence. "
                    "If the evidence does not contain the answer, say you don't know. "
                    "Respond in JSON format as an array of objects. "
                    'Each object must have a "sentence" key with the answer text and an "evidence_ids" '
                    "key with a list of evidence IDs that support that sentence. "
                    'Example: [{"sentence": "The answer is based on this source.", "evidence_ids": ["uuid"]}]'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {query.query_text}\n"
                    "Evidence:\n"
                    + "\n\n".join(
                        f"[ID: {ev['id']}] {ev['content']}" for ev in evidence_payloads
                    )
                ),
            },
        ]

        async for chunk in self._llm_client.generate_stream(messages):
            for sentence in parser.feed(chunk):
                await self._publish(query.id, "generating", {"sentence": sentence})

        parsed = parser.parse_final()
        if not parsed:
            return None
        return self._persist_answer_graph(session, query, parsed, evidence_payloads)

    def _persist_answer_graph(
        self,
        session,
        query: Query,
        parsed_sentences: list[dict[str, object]],
        evidence_payloads: list[dict[str, object]],
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

        full_text_parts = [str(item["sentence"]) for item in parsed_sentences]
        answer = Answer(
            id=uuid.uuid4(),
            query_id=query.id,
            full_text=" ".join(full_text_parts),
        )
        session.add(answer)

        sentence_payloads: list[dict[str, object]] = []

        for sentence_index, item in enumerate(parsed_sentences):
            sentence_text = str(item["sentence"])
            raw_evidence_ids = item.get("evidence_ids", [])
            if not isinstance(raw_evidence_ids, list):
                raise ValueError("evidence_ids must be a list")

            resolved: list[str] = []
            for raw in raw_evidence_ids:
                citation = _resolve_citation(raw)
                if citation:
                    resolved.append(citation)

            trace = SentenceTrace(
                id=uuid.uuid4(),
                answer_id=answer.id,
                sentence_index=sentence_index,
                sentence_text=sentence_text,
            )
            session.add(trace)
            for citation_index, evidence_id in enumerate(resolved):
                session.add(
                    SentenceTraceEvidence(
                        trace_id=trace.id,
                        evidence_id=uuid.UUID(evidence_id),
                        citation_index=citation_index,
                    )
                )

            sentence_payloads.append(
                {
                    "sentence_index": sentence_index,
                    "sentence_text": sentence_text,
                    "evidence_ids": resolved,
                }
            )
        return {
            "id": str(answer.id),
            "query_id": str(query.id),
            "full_text": answer.full_text,
            "sentences": sentence_payloads,
            "evidence": evidence_payloads,
        }

    async def _publish(self, query_id, event: str, data: Mapping[str, object]) -> None:
        channel = f"query:{query_id}:events"
        message = json.dumps({"event": event, "data": data})
        await self._redis.publish(channel, message)
