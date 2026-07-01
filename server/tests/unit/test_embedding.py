from __future__ import annotations

import httpx
import pytest

from typing import Any

from app.core.config import EmbeddingSettings
from app.infrastructure.embeddings.embedding import EmbeddingClient


def test_embed_texts_returns_vectors_in_input_order(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "data": [
                    {"embedding": [0.1, 0.2, 0.3]},
                    {"embedding": [0.4, 0.5, 0.6]},
                ]
            }

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.infrastructure.embeddings.embedding.httpx.post", fake_post)

    client = EmbeddingClient(
        EmbeddingSettings(
            api_base="http://optiplex-3020:8081/v1",
            api_key="1d58046a3b2c79ef",
            seed_demo_data=True,
            model="google/gemini-embedding-2",
            dimensions=768,
        )
    )

    vectors = client.embed_texts(["first", "second"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert captured["url"] == "http://optiplex-3020:8081/v1/embeddings"


def test_embed_texts_uses_correct_request_shape(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    def fake_post(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.infrastructure.embeddings.embedding.httpx.post", fake_post)

    client = EmbeddingClient(
        EmbeddingSettings(
            api_base="http://optiplex-3020:8081/v1",
            api_key="1d58046a3b2c79ef",
            seed_demo_data=True,
            model="google/gemini-embedding-2",
            dimensions=768,
        )
    )

    client.embed_texts(["first text"])

    assert captured["headers"]["Authorization"] == "Bearer 1d58046a3b2c79ef"
    assert captured["json"]["model"] == "google/gemini-embedding-2"
    assert captured["json"]["input"] == ["first text"]
    assert captured["json"]["dimensions"] == 768


def test_embed_texts_raises_on_non_200(monkeypatch) -> None:
    class FakeErrorResponse:
        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "401 Client Error",
                request=httpx.Request(
                    "POST", "http://optiplex-3020:8081/v1/embeddings"
                ),
                response=httpx.Response(401),
            )

    monkeypatch.setattr(
        "app.infrastructure.embeddings.embedding.httpx.post",
        lambda *a, **kw: FakeErrorResponse(),
    )

    client = EmbeddingClient(
        EmbeddingSettings(
            api_base="http://optiplex-3020:8081/v1",
            api_key="1d58046a3b2c79ef",
            seed_demo_data=True,
            model="google/gemini-embedding-2",
            dimensions=768,
        )
    )

    with pytest.raises(httpx.HTTPStatusError):
        client.embed_texts(["fail"])


class _MissingKeyResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"data": [{"not_embedding": [0.1]}]}


def test_embed_texts_raises_on_malformed_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.infrastructure.embeddings.embedding.httpx.post",
        lambda *a, **kw: _MissingKeyResponse(),
    )

    client = EmbeddingClient(
        EmbeddingSettings(
            api_base="http://optiplex-3020:8081/v1",
            api_key=None,
            seed_demo_data=True,
            model="google/gemini-embedding-2",
            dimensions=768,
        )
    )

    with pytest.raises(KeyError):
        client.embed_texts(["bad"])
