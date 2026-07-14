from __future__ import annotations

import pytest

from app.application.query_pipeline.arag_router import AragRouter, RoutingResult


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
@pytest.mark.parametrize(
    ("query", "response", "expected"),
    [
        (
            "What causes X, and how does that lead to Y?",
            '{"route": "multi_hop", "sub_queries": ["What causes X?", "How does X lead to Y?"]}',
            RoutingResult(
                route="multi_hop",
                sub_queries=["What causes X?", "How does X lead to Y?"],
            ),
        ),
        (
            "What was my last question in this thread?",
            '{"route": "conversation", "sub_queries": []}',
            RoutingResult(route="conversation", sub_queries=[]),
        ),
    ],
    ids=["multi-hop-with-sub-queries", "conversation-without-retrieval"],
)
async def test_arag_router_classify_parses_supported_routes(
    query: str,
    response: str,
    expected: RoutingResult,
) -> None:
    llm_client = _FakeLLMClient([response])
    router = AragRouter(llm_client=llm_client)

    assert await router.classify(query) == expected
    assert len(llm_client.calls) == 1


@pytest.mark.asyncio
async def test_arag_router_classify_parses_fenced_json_with_prose() -> None:
    fenced = (
        "Here is the classification:\n\n"
        "```json\n"
        '{"route": "comparison", "sub_queries": ["BERT pre-training", "GPT pre-training"]}\n'
        "```\n\n"
        "This is a comparison query.\n"
    )
    llm_client = _FakeLLMClient([fenced])
    router = AragRouter(llm_client=llm_client)

    assert await router.classify("Compare BERT and GPT") == RoutingResult(
        route="comparison",
        sub_queries=["BERT pre-training", "GPT pre-training"],
    )


@pytest.mark.asyncio
async def test_arag_router_classify_falls_back_to_simple_on_malformed_json() -> None:
    llm_client = _FakeLLMClient(["not json"])
    router = AragRouter(llm_client=llm_client)

    assert (
        await router.classify("Compare dense and sparse retrieval") == RoutingResult()
    )


@pytest.mark.asyncio
async def test_arag_router_classify_falls_back_to_simple_on_llm_error() -> None:
    llm_client = _FakeLLMClient([], error=TimeoutError("router timed out"))
    router = AragRouter(llm_client=llm_client)

    assert (
        await router.classify("Compare dense and sparse retrieval") == RoutingResult()
    )
