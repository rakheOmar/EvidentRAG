from __future__ import annotations

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
