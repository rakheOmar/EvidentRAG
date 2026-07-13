from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import RerankerSettings
from app.core.telemetry import traced_operation
from app.infrastructure.ai.scheduler import AIRequestScheduler


@dataclass(frozen=True)
class RerankResult:
    index: int
    relevance_score: float


class RerankClient:
    def __init__(
        self,
        settings: RerankerSettings,
        client: httpx.AsyncClient | None = None,
        scheduler: AIRequestScheduler | None = None,
    ) -> None:
        self._api_base = settings.api_base.rstrip("/")
        self._api_key = settings.api_key
        self._rerank_model = settings.model
        self._scheduler = scheduler
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        )

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_n: int = 5,
    ) -> list[RerankResult]:
        operation_context = {
            "model": self._rerank_model,
            "candidate_count": len(documents),
            "top_n": top_n,
        }

        with traced_operation("rerank", **operation_context) as operation:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            async def request() -> httpx.Response:
                response = await self._client.post(
                    f"{self._api_base}/rerank",
                    json={
                        "model": self._rerank_model,
                        "query": query,
                        "documents": documents,
                        "top_n": top_n,
                    },
                    headers=headers,
                )
                response.raise_for_status()
                return response

            response = (
                await self._scheduler.run("rerank", request)
                if self._scheduler is not None
                else await request()
            )
            response.raise_for_status()

            results = [
                RerankResult(
                    index=result["index"],
                    relevance_score=result["relevance_score"],
                )
                for result in response.json().get("results", [])
            ]
            operation["result_count"] = len(results)
            return sorted(
                results, key=lambda result: result.relevance_score, reverse=True
            )
