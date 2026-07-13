from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import EmbeddingSettings
from app.infrastructure.embeddings.embedding import EmbeddingClient


class _FakeModels:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def embed_content(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        contents = kwargs["contents"]
        return SimpleNamespace(
            embeddings=[
                SimpleNamespace(values=[float(index)]) for index in range(len(contents))
            ]
        )


class _FakeGenAIClient:
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key
        self.models = _FakeModels()


class _FakeScheduler:
    def __init__(self) -> None:
        self.buckets: list[str] = []

    async def run(self, bucket: str, operation):
        self.buckets.append(bucket)
        return await operation()


def _client(
    monkeypatch,
    fake: _FakeGenAIClient,
    *,
    batch_size: int = 64,
    scheduler: _FakeScheduler | None = None,
) -> EmbeddingClient:
    monkeypatch.setattr(
        "app.infrastructure.embeddings.embedding.genai.Client",
        lambda api_key: fake,
    )
    return EmbeddingClient(
        EmbeddingSettings(
            api_base="http://unused",
            api_key="gemini-key",
            seed_demo_data=True,
            model="gemini-embedding-2",
            dimensions=768,
            batch_size=batch_size,
        ),
        scheduler=scheduler,
    )


def test_embed_texts_uses_google_client_and_preserves_order(monkeypatch) -> None:
    fake = _FakeGenAIClient("gemini-key")
    client = _client(monkeypatch, fake)

    vectors = client.embed_texts(["first", "second"])

    assert vectors == [[0.0], [1.0]]
    call = fake.models.calls[0]
    assert call["model"] == "gemini-embedding-2"
    assert call["config"].output_dimensionality == 768
    assert [part.text for content in call["contents"] for part in content.parts] == [
        "first",
        "second",
    ]


def test_embed_images_uses_inline_image_parts(monkeypatch) -> None:
    fake = _FakeGenAIClient("gemini-key")
    client = _client(monkeypatch, fake)

    client.embed_images([b"png-bytes"])

    part = fake.models.calls[0]["contents"][0].parts[0]
    assert part.inline_data.data == b"png-bytes"
    assert part.inline_data.mime_type == "image/png"


def test_embed_texts_splits_requests_at_configured_batch_size(monkeypatch) -> None:
    fake = _FakeGenAIClient("gemini-key")
    client = _client(monkeypatch, fake)

    vectors = client.embed_texts([f"text-{index}" for index in range(161)])

    assert [len(call["contents"]) for call in fake.models.calls] == [64, 64, 33]
    assert len(vectors) == 161


@pytest.mark.asyncio
async def test_embed_texts_async_schedules_each_provider_batch(monkeypatch) -> None:
    fake = _FakeGenAIClient("gemini-key")
    scheduler = _FakeScheduler()
    client = _client(monkeypatch, fake, batch_size=2, scheduler=scheduler)

    vectors = await client.embed_texts_async(["first", "second", "third"])

    assert vectors == [[0.0], [1.0], [0.0]]
    assert scheduler.buckets == ["embeddings", "embeddings"]
    assert [len(call["contents"]) for call in fake.models.calls] == [2, 1]


@pytest.mark.asyncio
async def test_embed_texts_async_schedules_provider_retries(monkeypatch) -> None:
    fake = _FakeGenAIClient("gemini-key")
    scheduler = _FakeScheduler()
    attempts = 0

    def rate_limited_then_success(**kwargs: Any) -> SimpleNamespace:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED retry in 1.0s")
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.0]) for _ in kwargs["contents"]]
        )

    fake.models.embed_content = rate_limited_then_success  # type: ignore[method-assign]

    async def no_wait(_delay: float) -> None:
        return None

    monkeypatch.setattr(
        "app.infrastructure.embeddings.embedding.asyncio.sleep", no_wait
    )
    client = _client(monkeypatch, fake, scheduler=scheduler)

    assert await client.embed_texts_async(["retry me"]) == [[0.0]]
    assert scheduler.buckets == ["embeddings", "embeddings"]


def test_embed_texts_retries_provider_rate_limits(monkeypatch) -> None:
    fake = _FakeGenAIClient("gemini-key")
    attempts = 0
    delays: list[float] = []

    def rate_limited_then_success(**kwargs: Any) -> SimpleNamespace:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED retry in 38.0s")
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.0]) for _ in kwargs["contents"]]
        )

    fake.models.embed_content = rate_limited_then_success  # type: ignore[method-assign]
    monkeypatch.setattr("app.infrastructure.embeddings.embedding.sleep", delays.append)
    client = _client(monkeypatch, fake)

    assert client.embed_texts(["retry me"]) == [[0.0]]
    assert attempts == 2
    assert delays == [38.0]


def test_embed_texts_raises_when_google_returns_wrong_vector_count(monkeypatch) -> None:
    fake = _FakeGenAIClient("gemini-key")

    def invalid_response(**_: Any) -> SimpleNamespace:
        return SimpleNamespace(embeddings=[])

    fake.models.embed_content = invalid_response  # type: ignore[method-assign]
    client = _client(monkeypatch, fake)

    with pytest.raises(ValueError, match="contained 0 vectors for 1 inputs"):
        client.embed_texts(["bad"])
