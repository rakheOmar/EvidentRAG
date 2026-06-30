from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import LLMSettings


class LLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_base = settings.api_base.rstrip("/")
        self._api_key = settings.api_key
        self._generation_model = settings.generation_model
        self._utility_model = settings.utility_model
        self._client = client or httpx.AsyncClient()

    async def generate_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or self._generation_model

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        async with self._client.stream(
            "POST",
            f"{self._api_base}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    chunk = json.loads(data)
                    if (
                        content := chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    ):
                        yield content
