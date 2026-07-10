from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import monotonic, time
from typing import AsyncContextManager, TypeVar

import httpx
from redis.asyncio import Redis

from app.core.config import RateLimitSettings

T = TypeVar("T")


class AIRequestScheduler:
    """Coordinates provider capacity locally and across app processes."""

    def __init__(self, redis: Redis | None, settings: RateLimitSettings) -> None:
        self._redis = redis
        self._settings = settings
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    async def run(
        self,
        bucket: str,
        operation: Callable[[], Awaitable[T]],
        *,
        retry_window_seconds: float | None = None,
    ) -> T:
        deadline = monotonic() + (
            retry_window_seconds
            if retry_window_seconds is not None
            else self._settings.retry_window_seconds
        )
        attempt = 0

        while True:
            try:
                async with self.slot(bucket):
                    return await operation()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                    raise
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise
                await asyncio.sleep(_retry_delay(exc, attempt, remaining))
                attempt += 1

    async def stream(
        self,
        bucket: str,
        operation: Callable[[], AsyncContextManager[httpx.Response]],
        *,
        retry_window_seconds: float | None = None,
    ) -> AsyncIterator[str]:
        deadline = monotonic() + (
            retry_window_seconds
            if retry_window_seconds is not None
            else self._settings.retry_window_seconds
        )
        attempt = 0

        while True:
            emitted = False
            try:
                async with self.slot(bucket):
                    async with operation() as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_text():
                            emitted = True
                            yield chunk
                return
            except httpx.HTTPStatusError as exc:
                if emitted or exc.response.status_code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    raise
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise
                await asyncio.sleep(_retry_delay(exc, attempt, remaining))
                attempt += 1

    @asynccontextmanager
    async def slot(self, bucket: str) -> AsyncIterator[None]:
        semaphore = self._semaphores.get(bucket)
        if semaphore is None:
            semaphore = asyncio.Semaphore(_concurrency_for(bucket, self._settings))
            self._semaphores[bucket] = semaphore

        await semaphore.acquire()
        try:
            await self._acquire_distributed(bucket)
            yield
        finally:
            semaphore.release()

    async def _acquire_distributed(self, bucket: str) -> None:
        if self._redis is None:
            return

        limit = _requests_per_minute_for(bucket, self._settings)
        if limit <= 0:
            return

        key = f"evidentrag:ai-rate:{bucket}:{int(time() // 60)}"
        while True:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, 120)
            if count <= limit:
                return

            await self._redis.decr(key)
            ttl = await self._redis.ttl(key)
            await asyncio.sleep(max(0.1, min(float(ttl if ttl > 0 else 1), 5.0)))


def _retry_delay(exc: httpx.HTTPStatusError, attempt: int, remaining: float) -> float:
    retry_after = exc.response.headers.get("Retry-After")
    if retry_after is not None:
        try:
            return min(max(float(retry_after), 0.1), remaining)
        except ValueError:
            pass
    return min(max(0.25, (2**attempt) + random.uniform(0, 0.25)), remaining)


def _concurrency_for(bucket: str, settings: RateLimitSettings) -> int:
    if bucket == "llm:generation":
        return settings.generation_concurrency
    if bucket == "llm:utility":
        return settings.utility_concurrency
    if bucket == "embeddings":
        return settings.embedding_concurrency
    return settings.rerank_concurrency


def _requests_per_minute_for(bucket: str, settings: RateLimitSettings) -> int:
    if bucket == "llm:generation":
        return settings.generation_requests_per_minute
    if bucket == "llm:utility":
        return settings.utility_requests_per_minute
    if bucket == "embeddings":
        return settings.embedding_requests_per_minute
    return settings.rerank_requests_per_minute
