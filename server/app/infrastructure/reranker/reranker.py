from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import CohereSettings


@dataclass(frozen=True)
class RerankResult:
    index: int
    relevance_score: float


class RerankClient:
    def __init__(
        self,
        settings: CohereSettings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = settings.api_key
        self._rerank_model = settings.rerank_model
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        )

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[RerankResult]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        response = await self._client.post(
            "https://api.cohere.com/v2/rerank",
            json={
                "model": self._rerank_model,
                "query": query,
                "documents": documents,
                "top_n": top_n,
            },
            headers=headers,
        )
        response.raise_for_status()

        results = [
            RerankResult(
                index=result["index"],
                relevance_score=result["relevance_score"],
            )
            for result in response.json().get("results", [])
        ]
        return sorted(results, key=lambda result: result.relevance_score, reverse=True)
