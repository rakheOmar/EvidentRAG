from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import LLMSettings
from app.core.telemetry import traced_operation
from app.infrastructure.ai.scheduler import AIRequestScheduler
from app.infrastructure.llm.context_manager import ContextManager


class LLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        client: httpx.AsyncClient | None = None,
        scheduler: AIRequestScheduler | None = None,
    ) -> None:
        self._api_base = settings.api_base.rstrip("/")
        self._api_key = settings.api_key
        self._generation_model = settings.generation_model
        self._utility_model = settings.utility_model
        self._scheduler = scheduler
        self.context_manager = ContextManager(self._generation_model)
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        )

    async def generate(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> str:
        model = model or self._utility_model

        operation_context = {
            "model": model,
            "prompt_message_count": len(messages),
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        with traced_operation("llm.generate", **operation_context) as operation:

            async def request() -> httpx.Response:
                response = await self._client.post(
                    f"{self._api_base}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                return response

            bucket = (
                "llm:generation" if model == self._generation_model else "llm:utility"
            )
            response = (
                await self._scheduler.run(bucket, request)
                if self._scheduler is not None
                else await request()
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            operation["response_length"] = len(content)
            return content

    async def list_models(self) -> list[dict[str, object]]:
        """Load model metadata once so the API can serve context details locally."""
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        response = await self._client.get(
            f"{self._api_base}/models",
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        models = payload.get("data", []) if isinstance(payload, dict) else []
        return [model for model in models if isinstance(model, dict)]

    def set_model_catalog(self, model_catalog: list[dict[str, object]]) -> None:
        self.context_manager.set_model_catalog(model_catalog)

    async def generate_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncIterator[str]:
        model = model or self._generation_model

        operation_context = {
            "model": model,
            "prompt_message_count": len(messages),
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        raw_text = ""
        buffer = ""
        had_sse = False

        with traced_operation("llm.generate_stream", **operation_context) as operation:

            def request_stream():
                return self._client.stream(
                    "POST",
                    f"{self._api_base}/chat/completions",
                    json=payload,
                    headers=headers,
                )

            chunks = (
                self._scheduler.stream("llm:generation", request_stream)
                if self._scheduler is not None
                else _single_stream(request_stream)
            )
            async for chunk in chunks:
                raw_text += chunk
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.startswith("data: "):
                        had_sse = True
                        data = line[6:]
                        if data == "[DONE]":
                            continue
                        chunk_data = json.loads(data)
                        if (
                            content := chunk_data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        ):
                            yield content

            if buffer.startswith("data: "):
                had_sse = True
                data = buffer[6:]
                if data != "[DONE]":
                    try:
                        chunk_data = json.loads(data)
                        if (
                            content := chunk_data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        ):
                            yield content
                    except json.JSONDecodeError:
                        pass

            if not had_sse and raw_text:
                try:
                    data = json.loads(raw_text)
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    if content:
                        yield content
                except json.JSONDecodeError:
                    pass

            operation["response_length"] = len(raw_text)


async def _single_stream(operation) -> AsyncIterator[str]:
    async with operation() as response:
        response.raise_for_status()
        async for chunk in response.aiter_text():
            yield chunk
