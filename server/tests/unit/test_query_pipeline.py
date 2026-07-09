from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import cast

import pytest

from app.infrastructure.db.models import Message, Thread


class _FakeSession:
    def __init__(
        self, thread: Thread, user_message: Message, assistant_message: Message
    ) -> None:
        self.thread = thread
        self.user_message = user_message
        self.assistant_message = assistant_message
        self.committed_statuses: list[str] = []
        self.added_objects: list[object] = []
        self.execute_values: list[Message] = [self.user_message]

    async def scalar(self, statement):
        text = str(statement)
        if "FROM messages" in text and "messages.id" in text:
            return self.assistant_message
        if "FROM answers" in text:
            return None
        return None

    async def get(self, model, object_id):
        if model is Message and object_id == self.user_message.id:
            return self.user_message
        if model is Thread and object_id == self.thread.id:
            return self.thread
        return None

    async def execute(self, statement):
        return _FakeExecuteResult(self.execute_values)

    async def commit(self) -> None:
        self.committed_statuses.append(self.assistant_message.status)

    def add(self, obj: object) -> None:
        self.added_objects.append(obj)


class _FakeSessionContext:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> _FakeSession:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSessionFactory:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def __call__(self) -> _FakeSessionContext:
        return _FakeSessionContext(self._session)


class _FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))


def _make_thread_messages() -> tuple[Thread, Message, Message]:
    thread = Thread(title="What is BERT", summary="")
    thread.id = uuid.uuid4()
    thread.created_at = datetime.now(timezone.utc)
    thread.updated_at = thread.created_at

    user_message = Message(
        thread_id=thread.id,
        position=0,
        role="user",
        content_text="What is BERT?",
        status="completed",
        sub_queries=[],
    )
    user_message.id = uuid.uuid4()
    user_message.created_at = thread.created_at
    user_message.updated_at = thread.updated_at

    assistant_message = Message(
        thread_id=thread.id,
        reply_to_message_id=user_message.id,
        position=1,
        role="assistant",
        content_text="",
        status="pending",
        sub_queries=[],
    )
    assistant_message.id = uuid.uuid4()
    assistant_message.created_at = thread.created_at
    assistant_message.updated_at = thread.updated_at
    return thread, user_message, assistant_message


class _FakeConversationRouter:
    async def classify(self, query_text: str):
        class _Result:
            route = "conversation"
            sub_queries: list[str] = []

        return _Result()


class _FakeStreamingLLM:
    def __init__(self, stream_response: str) -> None:
        self.stream_response = stream_response
        self.stream_calls: list[list[dict[str, str]]] = []

    async def generate_stream(self, messages):
        self.stream_calls.append(messages)
        yield self.stream_response


def _read_event(redis: _FakeRedis, index: int) -> dict[str, object]:
    return json.loads(redis.published[index][1])


def test_query_pipeline_prompts_require_fluent_punctuated_segments() -> None:
    from app.application.query_pipeline.query_pipeline import (
        AGGREGATION_SYSTEM_PROMPT,
        COMPARISON_SYSTEM_PROMPT,
        CONVERSATION_SYSTEM_PROMPT,
        MULTI_HOP_SYSTEM_PROMPT,
        SIMPLE_SYSTEM_PROMPT,
    )

    expected_instruction = "joining the segments with spaces yields a fluent answer."

    for prompt in (
        SIMPLE_SYSTEM_PROMPT,
        MULTI_HOP_SYSTEM_PROMPT,
        COMPARISON_SYSTEM_PROMPT,
        AGGREGATION_SYSTEM_PROMPT,
        CONVERSATION_SYSTEM_PROMPT,
    ):
        assert "proper capitalization and punctuation" in prompt
        assert expected_instruction in prompt


@pytest.mark.asyncio
async def test_query_pipeline_run_marks_running_then_completed_and_publishes_events() -> (
    None
):
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    thread, user_message, assistant_message = _make_thread_messages()
    session = _FakeSession(thread, user_message, assistant_message)
    redis = _FakeRedis()

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
    )

    await pipeline.run(assistant_message.id)

    assert session.committed_statuses == ["running", "running", "completed"]
    assert assistant_message.status == "completed"
    assert assistant_message.completed_at is not None

    channel = f"message:{assistant_message.id}:events"
    assert [published_channel for published_channel, _ in redis.published] == [
        channel,
        channel,
        channel,
    ]

    first = _read_event(redis, 0)
    assert first["event"] == "route_selected"
    assert first["data"] == {"route": "simple", "sub_queries": []}

    second = _read_event(redis, 1)
    assert second["event"] == "content_parts"

    third = _read_event(redis, 2)
    assert third["event"] == "done"
    assert third["data"] == {
        "thread_id": str(thread.id),
        "message_id": str(assistant_message.id),
        "content_parts": [],
        "error": False,
    }


@pytest.mark.asyncio
async def test_query_pipeline_answers_conversation_route_from_thread_memory() -> None:
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    thread = Thread(title="What is BERT", summary="Earlier the user asked about BERT.")
    thread.id = uuid.uuid4()
    thread.created_at = datetime.now(timezone.utc)
    thread.updated_at = thread.created_at

    prior_user = Message(
        thread_id=thread.id,
        position=0,
        role="user",
        content_text="What is BERT?",
        status="completed",
        sub_queries=[],
    )
    prior_user.id = uuid.uuid4()
    prior_user.created_at = thread.created_at
    prior_user.updated_at = thread.updated_at

    user_message = Message(
        thread_id=thread.id,
        position=2,
        role="user",
        content_text="What was my last question?",
        status="completed",
        sub_queries=[],
    )
    user_message.id = uuid.uuid4()
    user_message.created_at = thread.created_at
    user_message.updated_at = thread.updated_at

    assistant_message = Message(
        thread_id=thread.id,
        reply_to_message_id=user_message.id,
        position=3,
        role="assistant",
        content_text="",
        status="pending",
        sub_queries=[],
    )
    assistant_message.id = uuid.uuid4()
    assistant_message.created_at = thread.created_at
    assistant_message.updated_at = thread.updated_at

    session = _FakeSession(thread, user_message, assistant_message)
    session.execute_values = [prior_user, user_message]
    redis = _FakeRedis()
    llm = _FakeStreamingLLM(
        '[{"text":"Your last question was \\"What is BERT?\\".","evidence_ids":[]}]'
    )

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
        llm_client=llm,
        arag_router=_FakeConversationRouter(),
    )

    await pipeline.run(assistant_message.id)

    route_event = _read_event(redis, 0)
    assert route_event["data"] == {"route": "conversation", "sub_queries": []}

    done_event = _read_event(redis, -1)
    done_data = cast(dict[str, object], done_event["data"])
    assert done_event["event"] == "done"
    assert done_data["error"] is False
    assert done_data["full_text"] == 'Your last question was "What is BERT?".'
    assert llm.stream_calls[0][0]["content"].startswith(
        "Answer the user's question using ONLY the provided conversation history"
    )


class _FakeExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._values)
