from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx

from app.core.config import RateLimitSettings
from app.infrastructure.ai.scheduler import AIRequestScheduler


def _settings() -> RateLimitSettings:
    return RateLimitSettings(
        retry_window_seconds=1,
        generation_requests_per_minute=20,
        utility_requests_per_minute=20,
        embedding_requests_per_minute=20,
        rerank_requests_per_minute=20,
        generation_concurrency=1,
        utility_concurrency=1,
        embedding_concurrency=1,
        rerank_concurrency=1,
    )


async def test_run_retries_transient_provider_failure(monkeypatch) -> None:
    scheduler = AIRequestScheduler(redis=None, settings=_settings())
    attempts = 0

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.HTTPStatusError(
                "rate limited",
                request=httpx.Request("POST", "https://provider.test"),
                response=httpx.Response(429),
            )
        return "ok"

    async def no_wait(_delay: float) -> None:
        return None

    monkeypatch.setattr("app.infrastructure.ai.scheduler.asyncio.sleep", no_wait)

    assert await scheduler.run("rerank", operation) == "ok"
    assert attempts == 2


async def test_embedding_bucket_uses_distributed_request_limit() -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.keys: list[str] = []

        async def incr(self, key: str) -> int:
            self.keys.append(key)
            return 1

        async def expire(self, key: str, seconds: int) -> None:
            return None

    redis = FakeRedis()
    settings = replace(
        _settings(),
        embedding_requests_per_minute=1,
        rerank_requests_per_minute=0,
    )
    scheduler = AIRequestScheduler(redis=redis, settings=settings)  # type: ignore[arg-type]

    assert await scheduler.run("embeddings", _return_ok) == "ok"
    assert len(redis.keys) == 1
    assert redis.keys[0].startswith("evidentrag:ai-rate:embeddings:")


async def test_embedding_bucket_uses_configured_concurrency() -> None:
    settings = replace(
        _settings(),
        embedding_concurrency=1,
        rerank_concurrency=2,
    )
    scheduler = AIRequestScheduler(redis=None, settings=settings)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def first_operation() -> str:
        first_started.set()
        await release_first.wait()
        return "first"

    async def second_operation() -> str:
        second_started.set()
        return "second"

    first = asyncio.create_task(scheduler.run("embeddings", first_operation))
    await first_started.wait()
    second = asyncio.create_task(scheduler.run("embeddings", second_operation))
    await asyncio.sleep(0)

    assert second_started.is_set() is False
    release_first.set()
    assert await asyncio.gather(first, second) == ["first", "second"]
    assert second_started.is_set() is True


async def _return_ok() -> str:
    return "ok"
