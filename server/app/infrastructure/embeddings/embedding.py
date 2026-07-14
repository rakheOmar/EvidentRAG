from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Sequence
from time import sleep
from typing import Any, Protocol, TypeVar

from google import genai
from google.genai import types

from app.core.config import EmbeddingSettings
from app.core.telemetry import record_degradation, traced_operation

MAX_EMBEDDING_REQUEST_SIZE = 100
MAX_EMBEDDING_RETRIES = 8
T = TypeVar("T")


class EmbeddingScheduler(Protocol):
    async def run(
        self,
        bucket: str,
        operation: Callable[[], Awaitable[T]],
    ) -> T: ...


class EmbeddingClient:
    def __init__(
        self,
        settings: EmbeddingSettings,
        scheduler: EmbeddingScheduler | None = None,
    ) -> None:
        self._model = settings.model
        self._dimensions = settings.dimensions
        self._scheduler = scheduler
        if settings.batch_size < 1:
            raise ValueError("Embedding batch size must be greater than zero")
        self._batch_size = min(settings.batch_size, MAX_EMBEDDING_REQUEST_SIZE)
        self._client = (
            genai.Client(
                api_key=settings.api_key,
                http_options=types.HttpOptions(base_url=settings.api_base),
            )
            if settings.api_key
            else None
        )

    def _models(self):
        if self._client is None:
            raise RuntimeError("GEMINI_API_KEY is required for embedding operations")
        return self._client.models

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        contents = [
            types.Content(parts=[types.Part.from_text(text=text)]) for text in texts
        ]
        return self._embed(contents, "embed_texts")

    def embed_images(self, images: list[bytes]) -> list[list[float]]:
        contents = [
            types.Content(
                parts=[types.Part.from_bytes(data=image, mime_type="image/png")]
            )
            for image in images
        ]
        return self._embed(contents, "embed_images")

    async def embed_texts_async(self, texts: list[str]) -> list[list[float]]:
        contents = [
            types.Content(parts=[types.Part.from_text(text=text)]) for text in texts
        ]
        return await self._embed_async(contents, "embed_texts")

    async def embed_images_async(self, images: list[bytes]) -> list[list[float]]:
        contents = [
            types.Content(
                parts=[types.Part.from_bytes(data=image, mime_type="image/png")]
            )
            for image in images
        ]
        return await self._embed_async(contents, "embed_images")

    def _embed(
        self,
        contents: Sequence[types.Content],
        event: str,
    ) -> list[list[float]]:
        results: list[list[float]] = []
        for start in range(0, len(contents), self._batch_size):
            results.extend(
                self._embed_batch(
                    contents[start : start + self._batch_size],
                    event,
                    start // self._batch_size + 1,
                    (len(contents) + self._batch_size - 1) // self._batch_size,
                )
            )
        return results

    async def _embed_async(
        self,
        contents: Sequence[types.Content],
        event: str,
    ) -> list[list[float]]:
        results: list[list[float]] = []
        batch_count = (len(contents) + self._batch_size - 1) // self._batch_size
        for start in range(0, len(contents), self._batch_size):
            batch = contents[start : start + self._batch_size]
            results.extend(
                await self._embed_batch_async(
                    batch,
                    event,
                    start // self._batch_size + 1,
                    batch_count,
                )
            )
        return results

    async def _embed_batch_async(
        self,
        contents: Sequence[types.Content],
        event: str,
        batch_number: int,
        batch_count: int,
    ) -> list[list[float]]:
        operation_context = {
            "model": self._model,
            "batch_size": len(contents),
            "batch_number": batch_number,
            "batch_count": batch_count,
        }
        with traced_operation(event, **operation_context) as operation:
            response = await self._embed_with_retries_async(contents, operation)
            result = [list(embedding.values) for embedding in response.embeddings]
            if len(result) != len(contents):
                raise ValueError(
                    f"Embedding response contained {len(result)} vectors for "
                    f"{len(contents)} inputs"
                )
            operation["embedding_count"] = len(result)
            return result

    def _embed_batch(
        self,
        contents: Sequence[types.Content],
        event: str,
        batch_number: int,
        batch_count: int,
    ) -> list[list[float]]:
        operation_context = {
            "model": self._model,
            "batch_size": len(contents),
            "batch_number": batch_number,
            "batch_count": batch_count,
        }
        with traced_operation(event, **operation_context) as operation:
            response = self._embed_with_retries(contents, operation)
            result = [list(embedding.values) for embedding in response.embeddings]
            if len(result) != len(contents):
                raise ValueError(
                    f"Embedding response contained {len(result)} vectors for "
                    f"{len(contents)} inputs"
                )
            operation["embedding_count"] = len(result)
            return result

    def _embed_with_retries(
        self,
        contents: Sequence[types.Content],
        wide_event: dict[str, object],
    ) -> Any:
        for attempt in range(MAX_EMBEDDING_RETRIES + 1):
            try:
                return self._models().embed_content(
                    model=self._model,
                    contents=list(contents),
                    config=types.EmbedContentConfig(
                        output_dimensionality=self._dimensions,
                    ),
                )
            except Exception as exc:
                if not self._is_rate_limited(exc) or attempt >= MAX_EMBEDDING_RETRIES:
                    raise
                delay = self._retry_delay(exc, attempt)
                wide_event["retry_count"] = attempt + 1
                wide_event["retry_delay_seconds"] = delay
                record_degradation(
                    "embedding_rate_limit",
                    model=self._model,
                    attempt=attempt + 1,
                    retry_delay_seconds=delay,
                )
                sleep(delay)

        raise AssertionError("Embedding retry loop exited unexpectedly")

    async def _embed_with_retries_async(
        self,
        contents: Sequence[types.Content],
        wide_event: dict[str, object],
    ) -> Any:
        for attempt in range(MAX_EMBEDDING_RETRIES + 1):

            async def request() -> Any:
                return await asyncio.to_thread(
                    self._models().embed_content,
                    model=self._model,
                    contents=list(contents),
                    config=types.EmbedContentConfig(
                        output_dimensionality=self._dimensions,
                    ),
                )

            try:
                return (
                    await self._scheduler.run("embeddings", request)
                    if self._scheduler is not None
                    else await request()
                )
            except Exception as exc:
                if not self._is_rate_limited(exc) or attempt >= MAX_EMBEDDING_RETRIES:
                    raise
                delay = self._retry_delay(exc, attempt)
                wide_event["retry_count"] = attempt + 1
                wide_event["retry_delay_seconds"] = delay
                record_degradation(
                    "embedding_rate_limit",
                    model=self._model,
                    attempt=attempt + 1,
                    retry_delay_seconds=delay,
                )
                await asyncio.sleep(delay)

        raise AssertionError("Embedding retry loop exited unexpectedly")

    @staticmethod
    def _is_rate_limited(exc: Exception) -> bool:
        message = str(exc).upper()
        return "429" in message or "RESOURCE_EXHAUSTED" in message

    @staticmethod
    def _retry_delay(exc: Exception, attempt: int) -> float:
        match = re.search(r"RETRY IN ([0-9.]+)S", str(exc).upper())
        if match:
            return min(float(match.group(1)), 120.0)
        return min(2.0 ** (attempt + 1), 120.0)
