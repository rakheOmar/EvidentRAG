from __future__ import annotations

import logging

from app.infrastructure.db.models import (
    Answer,
    Document,
    Evidence,
    SentenceTrace,
    SentenceTraceEvidence,
)


def _create_answer(client, *, query_id: str, full_text: str) -> None:
    session_factory = client.app.state.session_factory

    async def _persist() -> None:
        async with session_factory() as session:
            session.add(Answer(query_id=query_id, full_text=full_text))
            await session.commit()

    client.portal.call(_persist)


def _create_answer_graph(client, *, query_id: str) -> dict[str, str]:
    session_factory = client.app.state.session_factory
    slug_suffix = query_id[-8:]

    async def _persist() -> dict[str, str]:
        async with session_factory() as session:
            document = Document(
                title="Evidence Doc",
                slug=f"evidence-doc-{slug_suffix}",
                source_path=f"/tmp/evidence-doc-{slug_suffix}.pdf",
                content_hash="doc-hash",
                page_count=1,
            )
            evidence = Evidence(
                document=document,
                locator=f"evidence-doc-{slug_suffix}#page=1&chunk=0",
                content="Evidence content",
                content_hash="evidence-hash",
                context_header="Passage from Evidence Doc, page 1.",
                page=1,
                chunk_index=0,
                token_count=42,
            )
            answer = Answer(
                query_id=query_id, full_text="This is the completed answer."
            )
            sentence_trace = SentenceTrace(
                answer=answer,
                sentence_index=0,
                sentence_text="This is the completed answer.",
            )
            sentence_trace_evidence = SentenceTraceEvidence(
                trace=sentence_trace,
                evidence=evidence,
                citation_index=0,
            )
            session.add_all(
                [document, evidence, answer, sentence_trace, sentence_trace_evidence]
            )
            await session.commit()
            return {
                "answer_id": str(answer.id),
                "evidence_id": str(evidence.id),
            }

    return client.portal.call(_persist)


def test_health_preserves_incoming_request_id(client) -> None:
    response = client.get("/health", headers={"x-request-id": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-id"


def test_access_log_includes_request_metadata(client, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.access")

    response = client.get("/health", headers={"x-request-id": "log-test-id"})

    assert response.status_code == 200

    records = [record for record in caplog.records if record.name == "app.access"]
    assert len(records) == 1

    record = records[0]
    assert record.msg == "request_completed"
    assert record.http_method == "GET"
    assert record.http_path == "/health"
    assert record.http_status_code == 200
    assert record.request_id == "log-test-id"
    assert isinstance(record.duration_ms, float)


def test_create_query_returns_pending_simple_query(client) -> None:
    response = client.post(
        "/api/v1/queries",
        json={"query_text": "What does EvidentRAG say about citations?"},
    )

    assert response.status_code == 201

    body = response.json()
    assert body["id"]
    assert body["query_text"] == "What does EvidentRAG say about citations?"
    assert body["selected_route"] == "simple"
    assert body["status"] == "pending"
    assert body["error_message"] is None
    assert body["completed_at"] is None


def test_create_query_enqueues_pipeline_job(client) -> None:
    class FakeJobQueue:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def enqueue_job(self, function_name: str, query_id: str) -> None:
            self.calls.append((function_name, query_id))

    job_queue = FakeJobQueue()
    client.app.state.job_queue = job_queue

    response = client.post(
        "/api/v1/queries",
        json={"query_text": "Queue this query"},
    )

    assert response.status_code == 201

    query_id = response.json()["id"]
    assert job_queue.calls == [("run_query_pipeline", query_id)]


def test_get_query_returns_created_query(client) -> None:
    create_response = client.post(
        "/api/v1/queries",
        json={"query_text": "Where do citations come from?"},
    )
    query_id = create_response.json()["id"]

    response = client.get(f"/api/v1/queries/{query_id}")

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == query_id
    assert body["query_text"] == "Where do citations come from?"
    assert body["selected_route"] == "simple"
    assert body["status"] == "pending"
    assert body["error_message"] is None
    assert body["completed_at"] is None


def test_list_queries_returns_created_queries(client) -> None:
    first_response = client.post(
        "/api/v1/queries",
        json={"query_text": "First query"},
    )
    second_response = client.post(
        "/api/v1/queries",
        json={"query_text": "Second query"},
    )

    response = client.get("/api/v1/queries")

    assert response.status_code == 200

    body = response.json()
    returned_ids = {item["id"] for item in body}
    assert first_response.json()["id"] in returned_ids
    assert second_response.json()["id"] in returned_ids

    first_match = next(
        item for item in body if item["id"] == first_response.json()["id"]
    )
    second_match = next(
        item for item in body if item["id"] == second_response.json()["id"]
    )

    assert first_match["query_text"] == "First query"
    assert first_match["selected_route"] == "simple"
    assert first_match["status"] == "pending"
    assert first_match["error_message"] is None
    assert first_match["completed_at"] is None

    assert second_match["query_text"] == "Second query"
    assert second_match["selected_route"] == "simple"
    assert second_match["status"] == "pending"
    assert second_match["error_message"] is None
    assert second_match["completed_at"] is None


def test_get_query_answer_returns_accepted_while_pending(client) -> None:
    create_response = client.post(
        "/api/v1/queries",
        json={"query_text": "Answer not ready yet"},
    )
    query_id = create_response.json()["id"]

    response = client.get(f"/api/v1/queries/{query_id}/answer")

    assert response.status_code == 202
    assert response.json() == {"status": "pending"}


def test_get_query_answer_returns_completed_answer_when_present(client) -> None:
    create_response = client.post(
        "/api/v1/queries",
        json={"query_text": "What is the completed answer?"},
    )
    query_id = create_response.json()["id"]
    graph = _create_answer_graph(client, query_id=query_id)

    response = client.get(f"/api/v1/queries/{query_id}/answer")

    assert response.status_code == 200
    assert response.json() == {
        "id": graph["answer_id"],
        "query_id": query_id,
        "full_text": "This is the completed answer.",
        "sentences": [
            {
                "sentence_index": 0,
                "sentence_text": "This is the completed answer.",
                "evidence_ids": [graph["evidence_id"]],
            }
        ],
        "evidence": [
            {
                "id": graph["evidence_id"],
                "content": "Evidence content",
                "context_header": "Passage from Evidence Doc, page 1.",
                "document_title": "Evidence Doc",
                "document_slug": f"evidence-doc-{query_id[-8:]}",
                "page": 1,
            }
        ],
    }


def test_get_query_events_replays_done_for_completed_query(client) -> None:
    create_response = client.post(
        "/api/v1/queries",
        json={"query_text": "What does EvidentRAG say about citations?"},
    )
    query_id = create_response.json()["id"]
    graph = _create_answer_graph(client, query_id=query_id)

    with client.stream("GET", f"/api/v1/queries/{query_id}/events") as response:
        body = b"".join(response.iter_bytes())

    assert response.status_code == 200
    assert body.decode("utf-8") == (
        "event: done\n"
        f'data: {{"id":"{graph["answer_id"]}","query_id":"{query_id}",'
        '"full_text":"This is the completed answer.",'
        '"sentences":[{"sentence_index":0,"sentence_text":"This is the completed answer.",'
        f'"evidence_ids":["{graph["evidence_id"]}"]}}],'
        '"evidence":[{'
        f'"id":"{graph["evidence_id"]}",'
        '"content":"Evidence content",'
        '"context_header":"Passage from Evidence Doc, page 1.",'
        '"document_title":"Evidence Doc",'
        f'"document_slug":"evidence-doc-{query_id[-8:]}",'
        '"page":1}]}'
        "\n\n"
    )


def test_get_query_answer_returns_not_found_for_missing_query(client) -> None:
    response = client.get("/api/v1/queries/00000000-0000-0000-0000-000000000000/answer")

    assert response.status_code == 404
