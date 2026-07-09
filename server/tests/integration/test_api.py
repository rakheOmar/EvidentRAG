from __future__ import annotations

import json
import uuid

from app.infrastructure.db.models import (
    Answer,
    Document,
    Evidence,
    Message,
    Segment,
)


def _sse_done_event(
    answer_id: str, thread_id: str, message_id: str, evidence_id: str
) -> str:
    data = {
        "id": answer_id,
        "message_id": message_id,
        "thread_id": thread_id,
        "full_text": "This is the completed answer.",
        "reasoning_trace": [],
        "segments": [
            {
                "segment_index": 0,
                "text": "This is the completed answer.",
                "evidence_ids": [evidence_id],
            }
        ],
        "evidence": [
            {
                "id": evidence_id,
                "content": "Evidence content",
                "context_header": "Passage from Evidence Doc, page 1.",
                "document_title": "Evidence Doc",
                "document_slug": f"evidence-doc-{thread_id[-8:]}",
                "page": 1,
            }
        ],
        "content_parts": [
            {"type": "text", "text": "This is the completed answer."},
            {
                "type": "source",
                "sourceType": "document",
                "id": evidence_id,
                "title": "Evidence Doc",
                "mediaType": "text/plain",
                "providerMetadata": {
                    "evidentrag": {
                        "id": evidence_id,
                        "content": "Evidence content",
                        "document_title": "Evidence Doc",
                        "document_slug": f"evidence-doc-{thread_id[-8:]}",
                        "page": 1,
                        "context_header": "Passage from Evidence Doc, page 1.",
                    }
                },
                "filename": f"evidence-doc-{thread_id[-8:]}.txt",
            },
        ],
        "error": False,
    }
    return f"event: done\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def _parse_sse_done_event(payload: str) -> dict[str, object]:
    prefix = "event: done\ndata: "
    assert payload.startswith(prefix)
    return json.loads(payload[len(prefix) :].strip())


def _create_answer_graph(client, *, thread_id: str, message_id: str) -> dict[str, str]:
    session_factory = client.app.state.session_factory
    slug_suffix = thread_id[-8:]

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
                id=uuid.uuid4(),
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
                message_id=message_id, full_text="This is the completed answer."
            )
            segment = Segment(
                answer=answer,
                segment_index=0,
                text="This is the completed answer.",
                evidence_ids=[str(evidence.id)],
            )
            message = await session.get(Message, uuid.UUID(message_id))
            if message is not None:
                message.status = "completed"
            session.add_all([document, evidence, answer, segment, message])
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


def test_create_thread_returns_pending_turn(client) -> None:
    response = client.post(
        "/api/v1/threads",
        json={"content": "What does EvidentRAG say about citations?"},
    )

    assert response.status_code == 201

    body = response.json()
    assert body["thread"]["id"]
    assert (
        body["user_message"]["content_text"]
        == "What does EvidentRAG say about citations?"
    )
    assert body["assistant_message"]["status"] == "pending"


def test_append_message_enqueues_pipeline_job(client) -> None:
    class FakeJobQueue:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def enqueue_job(self, function_name: str, message_id: str) -> None:
            self.calls.append((function_name, message_id))

    job_queue = FakeJobQueue()
    client.app.state.job_queue = job_queue

    create_response = client.post(
        "/api/v1/threads",
        json={"content": "First message"},
    )
    thread_id = create_response.json()["thread"]["id"]

    response = client.post(
        f"/api/v1/threads/{thread_id}/messages",
        json={"content": "Second message"},
    )

    assert response.status_code == 201
    message_id = response.json()["assistant_message"]["id"]
    assert job_queue.calls[-1] == ("run_message_pipeline", message_id)


def test_list_threads_returns_created_threads(client) -> None:
    first_response = client.post("/api/v1/threads", json={"content": "First thread"})
    second_response = client.post("/api/v1/threads", json={"content": "Second thread"})

    response = client.get("/api/v1/threads")

    assert response.status_code == 200

    body = response.json()
    returned_ids = {item["id"] for item in body}
    assert first_response.json()["thread"]["id"] in returned_ids
    assert second_response.json()["thread"]["id"] in returned_ids


def test_get_thread_returns_full_message_history(client) -> None:
    create_response = client.post("/api/v1/threads", json={"content": "What is BERT?"})
    thread_id = create_response.json()["thread"]["id"]

    response = client.get(f"/api/v1/threads/{thread_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == thread_id
    assert [message["role"] for message in body["messages"]] == ["user", "assistant"]


def test_get_message_events_replays_done_for_completed_message(client) -> None:
    create_response = client.post(
        "/api/v1/threads",
        json={"content": "What does EvidentRAG say about citations?"},
    )
    thread_id = create_response.json()["thread"]["id"]
    message_id = create_response.json()["assistant_message"]["id"]
    graph = _create_answer_graph(client, thread_id=thread_id, message_id=message_id)

    with client.stream(
        "GET",
        f"/api/v1/threads/{thread_id}/messages/{message_id}/events",
    ) as response:
        body = b"".join(response.iter_bytes())

    assert response.status_code == 200
    actual_payload = _parse_sse_done_event(body.decode("utf-8"))
    expected_payload = _parse_sse_done_event(
        _sse_done_event(graph["answer_id"], thread_id, message_id, graph["evidence_id"])
    )
    assert actual_payload["id"] == expected_payload["id"]
    assert actual_payload["thread_id"] == expected_payload["thread_id"]
    assert actual_payload["message_id"] == expected_payload["message_id"]
    assert actual_payload["full_text"] == expected_payload["full_text"]
    assert actual_payload["segments"] == expected_payload["segments"]
    assert actual_payload["evidence"] == expected_payload["evidence"]
    assert actual_payload["error"] is False


def test_get_thread_returns_not_found_for_missing_thread(client) -> None:
    response = client.get("/api/v1/threads/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
