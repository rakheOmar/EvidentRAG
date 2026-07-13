from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import cast

import pytest
from starlette.requests import Request

from app.api.routes.threads import _generate_thread_title, create_thread
from app.api.schemas.threads import ThreadCreate
from app.infrastructure.db.models import Message, Thread


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False

    def add(self, obj: object) -> None:
        if isinstance(obj, Thread) and obj.id is None:
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = obj.created_at
        if isinstance(obj, Message) and obj.id is None:
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = obj.created_at
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if isinstance(obj, (Thread, Message)) and obj.id is None:
                obj.id = uuid.uuid4()

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: object) -> None:
        return None

    async def get(self, model, object_id):
        for obj in self.added:
            if isinstance(obj, model) and getattr(obj, "id", None) == object_id:
                return obj
        return None

    async def scalar(self, statement):
        text = str(statement)
        if "coalesce" in text:
            return 0
        return None


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


class _FakeJobQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    async def enqueue_job(
        self,
        function_name: str,
        message_id: str,
        trace_context: dict[str, str],
    ) -> None:
        self.calls.append((function_name, message_id, trace_context))


class _FakeLLMClient:
    async def generate(self, messages, model=None) -> str:
        return "Thread title"


class _MarkdownTitleLLMClient:
    async def generate(self, messages, model=None) -> str:
        return "## Figure 2: BERT Embeddings\n\n| Type | Purpose |"


@pytest.mark.asyncio
async def test_generate_thread_title_strips_markdown_from_model_output() -> None:
    request = cast(
        Request,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(llm_client=_MarkdownTitleLLMClient())
            )
        ),
    )

    title = await _generate_thread_title(request, "Explain Figure 2")

    assert title == "Figure 2: BERT Embeddings"


@pytest.mark.asyncio
async def test_generate_thread_title_strips_markdown_from_fallback() -> None:
    request = cast(
        Request,
        SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(llm_client=None))),
    )

    title = await _generate_thread_title(request, "## Explain BERT\n\nMore detail")

    assert title == "Explain BERT"


@pytest.mark.asyncio
async def test_create_thread_enqueues_message_pipeline_job_when_queue_is_configured() -> (
    None
):
    session = _FakeSession()
    job_queue = _FakeJobQueue()
    request = cast(
        Request,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    session_factory=_FakeSessionFactory(session),
                    job_queue=job_queue,
                    llm_client=_FakeLLMClient(),
                )
            )
        ),
    )

    response = await create_thread(ThreadCreate(content="Queue this thread"), request)

    assert session.committed is True
    assert response.thread.title == "Thread title"
    assert response.user_message.role == "user"
    assert response.assistant_message.role == "assistant"
    assert job_queue.calls == [
        ("run_message_pipeline", str(response.assistant_message.id), {})
    ]
