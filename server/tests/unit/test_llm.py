from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from app.core.config import LLMSettings
from app.infrastructure.llm.llm import LLMClient


class _MockResponse:
    def __init__(
        self,
        lines: list[str],
        status_code: int = 200,
    ) -> None:
        self._lines = lines
        self._status_code = status_code

    def raise_for_status(self) -> None:
        if self._status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self._status_code} Client Error",
                request=httpx.Request(
                    "POST", "http://optiplex-3020:8081/v1/chat/completions"
                ),
                response=httpx.Response(self._status_code),
            )

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


class _MockStreamContext:
    def __init__(self, lines: list[str], status_code: int = 200) -> None:
        self._response = _MockResponse(lines, status_code=status_code)

    async def __aenter__(self) -> _MockResponse:
        return self._response

    async def __aexit__(self, *args: Any) -> None:
        pass


class _MockAsyncClient:
    def __init__(self) -> None:
        self.last_stream_kwargs: dict[str, Any] = {}
        self._lines: list[str] = []
        self._status_code: int = 200

    def set_response_lines(self, lines: list[str]) -> None:
        self._lines = lines

    def set_status_code(self, status_code: int) -> None:
        self._status_code = status_code

    def stream(self, method: str, url: str, **kwargs: Any) -> _MockStreamContext:
        self.last_stream_kwargs = {"method": method, "url": url, **kwargs}
        return _MockStreamContext(self._lines, status_code=self._status_code)


_DEFAULT_SETTINGS = LLMSettings(
    api_base="http://optiplex-3020:8081/v1",
    api_key="test-key",
    generation_model="gemini-2.5-pro",
    utility_model="gemini-2.5-flash",
)


def _make_client(mock_client: Any = None) -> LLMClient:
    return LLMClient(
        settings=_DEFAULT_SETTINGS,
        client=mock_client or _MockAsyncClient(),  # type: ignore[reportArgumentType]
    )


async def test_generate_stream_yields_tokens() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_response_lines(
        [
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            "data: [DONE]",
        ]
    )

    client = _make_client(mock_client)
    tokens = [
        t async for t in client.generate_stream([{"role": "user", "content": "hi"}])
    ]

    assert tokens == ["Hello", " world"]


async def test_generate_stream_sends_correct_request() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_response_lines(["data: [DONE]"])

    client = _make_client(mock_client)
    async for _ in client.generate_stream([{"role": "user", "content": "hi"}]):
        pass

    kwargs = mock_client.last_stream_kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["url"] == "http://optiplex-3020:8081/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == "gemini-2.5-pro"
    assert kwargs["json"]["messages"] == [{"role": "user", "content": "hi"}]
    assert kwargs["json"]["stream"] is True


async def test_generate_stream_raises_on_non_200() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_status_code(401)

    client = _make_client(mock_client)
    with pytest.raises(httpx.HTTPStatusError):
        async for _ in client.generate_stream([{"role": "user", "content": "hi"}]):
            pass


async def test_generate_stream_defaults_to_generation_model() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_response_lines(["data: [DONE]"])

    client = _make_client(mock_client)
    async for _ in client.generate_stream([{"role": "user", "content": "hi"}]):
        pass

    assert mock_client.last_stream_kwargs["json"]["model"] == "gemini-2.5-pro"


async def test_generate_stream_uses_explicit_model() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_response_lines(["data: [DONE]"])

    client = _make_client(mock_client)
    async for _ in client.generate_stream(
        [{"role": "user", "content": "hi"}], model="gemini-2.5-flash"
    ):
        pass

    assert mock_client.last_stream_kwargs["json"]["model"] == "gemini-2.5-flash"


async def test_generate_stream_skips_missing_content() -> None:
    mock_client = _MockAsyncClient()
    mock_client.set_response_lines(
        [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":"only me"}}]}',
            "data: [DONE]",
        ]
    )

    client = _make_client(mock_client)
    tokens = [
        t async for t in client.generate_stream([{"role": "user", "content": "hi"}])
    ]

    assert tokens == ["only me"]
