from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.config import CohereSettings
from app.infrastructure.reranker.reranker import RerankClient


class _MockResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self._status_code = status_code

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self._status_code} Client Error",
                request=httpx.Request("POST", "https://api.cohere.com/v2/rerank"),
                response=httpx.Response(self._status_code),
            )

    def json(self) -> dict[str, Any]:
        return self._json_data


class _MockAsyncClient:
    def __init__(self) -> None:
        self.last_post_kwargs: dict[str, Any] = {}
        self._json_data: dict[str, Any] = {"results": []}
        self._status_code = 200

    def set_response(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self._status_code = status_code

    async def post(self, url: str, **kwargs: Any) -> _MockResponse:
        self.last_post_kwargs = {"url": url, **kwargs}
        return _MockResponse(self._json_data, status_code=self._status_code)


_DEFAULT_SETTINGS = CohereSettings(
    api_key="cohere-test-key",
    rerank_model="rerank-english-v3.0",
)


def _make_client(mock_client: Any = None) -> RerankClient:
    return RerankClient(
        settings=_DEFAULT_SETTINGS,
        client=mock_client or _MockAsyncClient(),  # type: ignore[reportArgumentType]
    )


async def test_rerank_sends_correct_request_and_parses_results() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_response(
        {
            "results": [
                {"index": 2, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.72},
            ]
        }
    )

    client = _make_client(mock_client)
    results = await client.rerank(
        query="What is EvidentRAG?",
        documents=["doc one", "doc two", "doc three"],
        top_n=2,
    )

    assert [result.index for result in results] == [2, 0]
    assert [result.relevance_score for result in results] == [0.95, 0.72]

    kwargs = mock_client.last_post_kwargs
    assert kwargs["url"] == "https://api.cohere.com/v2/rerank"
    assert kwargs["headers"]["Authorization"] == "Bearer cohere-test-key"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert kwargs["json"] == {
        "model": "rerank-english-v3.0",
        "query": "What is EvidentRAG?",
        "documents": ["doc one", "doc two", "doc three"],
        "top_n": 2,
    }


async def test_rerank_raises_on_non_200() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_response({"message": "unauthorized"}, status_code=401)

    client = _make_client(mock_client)
    with pytest.raises(httpx.HTTPStatusError):
        await client.rerank(query="hi", documents=["doc one"])
