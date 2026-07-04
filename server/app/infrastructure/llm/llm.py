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
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        )

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

        raw_text = ""

        async with self._client.stream(
            "POST",
            f"{self._api_base}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_text():
                raw_text += chunk

        lines = raw_text.split("\n")
        had_sse = any(line.startswith("data: ") for line in lines)

        if had_sse:
            for line in lines:
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        continue
                    chunk = json.loads(data)
                    if (
                        content := chunk.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content")
                    ):
                        yield content
        else:
            try:
                data = json.loads(raw_text)
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                if content:
                    yield content
            except json.JSONDecodeError:
                pass
