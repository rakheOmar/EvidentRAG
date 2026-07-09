from __future__ import annotations

import pytest


class _FakeLLMClient:
    def __init__(self, responses: list[str], *, error: Exception | None = None) -> None:
        self._responses = responses
        self._error = error
        self.calls: list[dict[str, object]] = []

    async def generate(self, messages, model=None) -> str:
        self.calls.append({"messages": messages, "model": model})
        if self._error is not None:
            raise self._error
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_arag_router_classify_returns_valid_route_and_sub_queries() -> None:
    from app.application.query_pipeline.arag_router import AragRouter

    llm_client = _FakeLLMClient(
        [
            '{"route": "multi_hop", "sub_queries": ["What causes X?", "How does X lead to Y?"]}'
        ]
    )
    router = AragRouter(llm_client=llm_client)

    result = await router.classify("What causes X, and how does that lead to Y?")

    assert result.route == "multi_hop"
    assert result.sub_queries == ["What causes X?", "How does X lead to Y?"]
    assert len(llm_client.calls) == 1


@pytest.mark.asyncio
async def test_arag_router_classify_falls_back_to_simple_on_malformed_json() -> None:
    from app.application.query_pipeline.arag_router import AragRouter

    llm_client = _FakeLLMClient(["not json"])
    router = AragRouter(llm_client=llm_client)

    result = await router.classify("Compare dense and sparse retrieval")

    assert result.route == "simple"
    assert result.sub_queries == []


@pytest.mark.asyncio
async def test_arag_router_classify_falls_back_to_simple_on_llm_error() -> None:
    from app.application.query_pipeline.arag_router import AragRouter

    llm_client = _FakeLLMClient([], error=TimeoutError("router timed out"))
    router = AragRouter(llm_client=llm_client)

    result = await router.classify("Summarize the document")

    assert result.route == "simple"
    assert result.sub_queries == []
