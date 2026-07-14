from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Protocol, cast

import pytest
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.orm.exc import StaleDataError

from app.infrastructure.db.models import Message, Thread


@pytest.fixture(autouse=True)
def _disable_event_throttling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.application.query_pipeline.query_pipeline.MIN_EVENT_INTERVAL_S", 0.0
    )


class _AssistantMessageLike(Protocol):
    id: uuid.UUID
    role: str
    reply_to_message_id: uuid.UUID | None
    thread_id: uuid.UUID
    status: str
    selected_route: str | None
    sub_queries: list
    error_message: str | None
    updated_at: datetime
    completed_at: datetime | None


class _FakeSession:
    def __init__(
        self,
        thread: Thread,
        user_message: Message,
        assistant_message: _AssistantMessageLike,
    ) -> None:
        self.thread = thread
        self.user_message = user_message
        self.assistant_message = assistant_message
        self._assistant_message_id = assistant_message.id
        self.committed_statuses: list[str] = []
        self.added_objects: list[object] = []
        self.execute_values: list[Message] = [self.user_message]
        self.fail_commit_at: int | None = None
        self.commit_attempts = 0
        self.rollback_calls = 0
        self._needs_rollback = False
        self.expire_identity_after_rollback = False

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
        if model is Message and object_id == self._assistant_message_id:
            return self.assistant_message
        if model is Thread and object_id == self.thread.id:
            return self.thread
        return None

    async def execute(self, statement):
        return _FakeExecuteResult(self.execute_values)

    async def commit(self) -> None:
        if self._needs_rollback:
            raise PendingRollbackError("session is in failed transaction state")
        self.commit_attempts += 1
        if self.fail_commit_at == self.commit_attempts:
            self._needs_rollback = True
            raise StaleDataError(
                "UPDATE statement on table 'messages' expected to update 1 row(s); 0 were matched."
            )
        self.committed_statuses.append(self.assistant_message.status)

    async def rollback(self) -> None:
        self.rollback_calls += 1
        self._needs_rollback = False
        if self.expire_identity_after_rollback and hasattr(
            self.assistant_message, "mark_identity_expired"
        ):
            cast(
                _FragileAssistantMessage, self.assistant_message
            ).mark_identity_expired()

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


class _TokenSessionContext:
    def __init__(self, session: object) -> None:
        self._session = session

    async def __aenter__(self) -> object:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _TokenSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[object] = []

    def __call__(self) -> _TokenSessionContext:
        session = object()
        self.sessions.append(session)
        return _TokenSessionContext(session)


class _FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))


class _FragileAssistantMessage:
    def __init__(self, message: Message) -> None:
        self._message = message
        self._identity_expired = False

    def mark_identity_expired(self) -> None:
        self._identity_expired = True

    @property
    def id(self) -> uuid.UUID:
        if self._identity_expired:
            raise PendingRollbackError(
                "assistant identity access should not happen after rollback"
            )
        return self._message.id

    @property
    def role(self) -> str:
        return self._message.role

    @property
    def reply_to_message_id(self) -> uuid.UUID | None:
        return self._message.reply_to_message_id

    @property
    def thread_id(self) -> uuid.UUID:
        return self._message.thread_id

    @property
    def status(self) -> str:
        return self._message.status

    @status.setter
    def status(self, value: str) -> None:
        self._message.status = value

    @property
    def selected_route(self) -> str | None:
        return self._message.selected_route

    @selected_route.setter
    def selected_route(self, value: str | None) -> None:
        self._message.selected_route = value

    @property
    def sub_queries(self) -> list:
        return self._message.sub_queries

    @sub_queries.setter
    def sub_queries(self, value: list) -> None:
        self._message.sub_queries = value

    @property
    def error_message(self) -> str | None:
        return self._message.error_message

    @error_message.setter
    def error_message(self, value: str | None) -> None:
        self._message.error_message = value

    @property
    def updated_at(self):
        return self._message.updated_at

    @updated_at.setter
    def updated_at(self, value) -> None:
        self._message.updated_at = value

    @property
    def completed_at(self):
        return self._message.completed_at

    @completed_at.setter
    def completed_at(self, value) -> None:
        self._message.completed_at = value


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


def test_query_pipeline_prompts_require_markdown_safe_segments() -> None:
    from app.application.query_pipeline.query_pipeline import (
        AGGREGATION_SYSTEM_PROMPT,
        COMPARISON_SYSTEM_PROMPT,
        CONVERSATION_SYSTEM_PROMPT,
        MULTI_HOP_SYSTEM_PROMPT,
        SIMPLE_SYSTEM_PROMPT,
    )

    for prompt in (
        SIMPLE_SYSTEM_PROMPT,
        MULTI_HOP_SYSTEM_PROMPT,
        COMPARISON_SYSTEM_PROMPT,
        AGGREGATION_SYSTEM_PROMPT,
        CONVERSATION_SYSTEM_PROMPT,
    ):
        assert "proper capitalization and punctuation" in prompt
        assert "Never split a Markdown construct across objects" in prompt


def test_query_pipeline_preserves_markdown_block_boundaries_when_joining_segments() -> (
    None
):
    from app.application.query_pipeline.json_stream_parser import join_segment_texts

    segments = [
        "## Figure 2 Explanation",
        "| Embedding Type | Purpose | Example |\n|---|---|---|\n| Token | Captures lexical semantics | $E_{token}$ |\n",
        "**Figure 2:** The input embeddings are summed.",
        "For each token, the representation is denoted as $E_i$.",
        "$$E_i = E_{token} + E_{segment} + E_{position}$$",
        "1. Tokenize the sentence.",
        "2. Add a segment embedding.",
        "```python\nE[i] = token_emb[i] + segment_emb[i]\n```",
    ]

    assert join_segment_texts(segments) == (
        "## Figure 2 Explanation\n\n"
        "| Embedding Type | Purpose | Example |\n"
        "|---|---|---|\n"
        "| Token | Captures lexical semantics | $E_{token}$ |\n\n"
        "**Figure 2:** The input embeddings are summed. "
        "For each token, the representation is denoted as $E_i$.\n\n"
        "$$E_i = E_{token} + E_{segment} + E_{position}$$\n\n"
        "1. Tokenize the sentence.\n"
        "2. Add a segment embedding.\n\n"
        "```python\nE[i] = token_emb[i] + segment_emb[i]\n```"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["comparison", "aggregation"])
async def test_parallel_routes_isolate_database_sessions(route: str) -> None:
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    class RecordingPipeline(QueryPipeline):
        def __init__(self, session_factory) -> None:
            super().__init__(session_factory=session_factory, redis=_FakeRedis())
            self.retrieval_sessions: list[object] = []

        async def _retrieve_evidence(self, session, *args, **kwargs):
            self.retrieval_sessions.append(session)
            return [], [], {}

    session_factory = _TokenSessionFactory()
    pipeline = RecordingPipeline(session_factory)
    main_session = object()
    message = cast(Message, type("MessageStub", (), {"id": uuid.uuid4()})())
    route_method = getattr(pipeline, f"_run_{route}_route")

    await route_method(
        main_session,
        message,
        "Compare BERT and transformers",
        None,
        ["BERT", "transformers"],
    )

    assert len(pipeline.retrieval_sessions) == 2
    assert len({id(session) for session in pipeline.retrieval_sessions}) == 2
    assert main_session not in pipeline.retrieval_sessions


@pytest.mark.asyncio
async def test_retrieval_rejects_qdrant_points_not_current_in_postgres() -> None:
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    allowed_id = uuid.uuid4()
    stale_id = uuid.uuid4()
    session = SimpleNamespace(
        execute=lambda _statement: None,
    )

    async def execute(_statement):
        return _FakeExecuteResult([allowed_id])

    session.execute = execute
    pipeline = QueryPipeline(session_factory=None, redis=_FakeRedis())
    points = [
        SimpleNamespace(payload={"evidence_id": str(allowed_id)}),
        SimpleNamespace(payload={"evidence_id": str(stale_id)}),
    ]

    filtered = await pipeline._filter_retrievable_points(session, points)

    assert filtered == [points[0]]


@pytest.mark.asyncio
async def test_query_pipeline_run_marks_running_then_completed_and_publishes_events() -> (
    None
):
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    thread, user_message, assistant_message = _make_thread_messages()
    session = _FakeSession(
        thread, user_message, cast(_AssistantMessageLike, assistant_message)
    )
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

    session = _FakeSession(
        thread, user_message, cast(_AssistantMessageLike, assistant_message)
    )
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


@pytest.mark.asyncio
async def test_query_pipeline_rolls_back_before_marking_failed() -> None:
    from app.application.query_pipeline.query_pipeline import QueryPipeline

    thread, user_message, assistant_message = _make_thread_messages()
    session = _FakeSession(
        thread,
        user_message,
        _FragileAssistantMessage(assistant_message),  # type: ignore[arg-type]
    )
    session.fail_commit_at = 2
    session.expire_identity_after_rollback = True
    redis = _FakeRedis()

    pipeline = QueryPipeline(
        session_factory=_FakeSessionFactory(session),
        redis=redis,
    )

    with pytest.raises(StaleDataError):
        await pipeline.run(assistant_message.id)

    assert session.rollback_calls == 1
    assert session.committed_statuses == ["running", "failed"]
    assert assistant_message.status == "failed"

    done_event = _read_event(redis, -1)
    done_data = cast(dict[str, object], done_event["data"])
    assert done_event["event"] == "done"
    assert done_data["error"] is True
    assert done_data["error_message"] == (
        "UPDATE statement on table 'messages' expected to update 1 row(s); 0 were matched."
    )


class _FakeExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._values)
