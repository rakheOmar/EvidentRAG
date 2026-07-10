from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from time import perf_counter

import httpx

from app.core.config import LLMSettings
from app.infrastructure.ai.scheduler import AIRequestScheduler
from app.infrastructure.llm.context_manager import ContextManager

logger = logging.getLogger(__name__)


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
        started_at = perf_counter()
        model = model or self._utility_model

        wide_event: dict[str, object] = {
            "event": "llm_generate",
            "model": model,
            "prompt_messages": len(messages),
        }

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        try:

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
            wide_event["response_length"] = len(content)
            wide_event["outcome"] = "success"
            return content
        except Exception as exc:
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            raise
        finally:
            wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            logger.info("llm_generate", extra={"wide_event": wide_event})

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
        started_at = perf_counter()
        model = model or self._generation_model

        wide_event: dict[str, object] = {
            "event": "llm_generate_stream",
            "model": model,
            "prompt_messages": len(messages),
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

        try:

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

            wide_event["response_length"] = len(raw_text)
            wide_event["outcome"] = "success"
        except Exception as exc:
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            raise
        finally:
            wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            logger.info("llm_generate_stream", extra={"wide_event": wide_event})


async def _single_stream(operation) -> AsyncIterator[str]:
    async with operation() as response:
        response.raise_for_status()
        async for chunk in response.aiter_text():
            yield chunk
