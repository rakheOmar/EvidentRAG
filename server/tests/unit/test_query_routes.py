from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from starlette.requests import Request

from app.api.routes.queries import create_query
from app.api.schemas.queries import QueryCreate
from app.infrastructure.db.models import Query


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.committed = False
        self.refreshed: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, obj: object) -> None:
        assert isinstance(obj, Query)
        obj.id = uuid.uuid4()
        self.refreshed.append(obj)


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
        self.calls: list[tuple[str, str]] = []

    async def enqueue_job(self, function_name: str, query_id: str) -> None:
        self.calls.append((function_name, query_id))


@pytest.mark.asyncio
async def test_create_query_enqueues_pipeline_job_when_queue_is_configured() -> None:
    session = _FakeSession()
    job_queue = _FakeJobQueue()
    request = cast(
        Request,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    session_factory=_FakeSessionFactory(session),
                    job_queue=job_queue,
                )
            )
        ),
    )

    query = await create_query(QueryCreate(query_text="Queue this query"), request)

    assert session.committed is True
    assert session.refreshed == [query]
    assert job_queue.calls == [("run_query_pipeline", str(query.id))]
