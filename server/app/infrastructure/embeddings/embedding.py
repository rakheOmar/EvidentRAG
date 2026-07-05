from __future__ import annotations

import logging
from time import perf_counter

import httpx

from app.core.config import EmbeddingSettings

logger = logging.getLogger(__name__)

EMBEDDING_REQUEST_TIMEOUT_SECONDS = 120.0


class EmbeddingClient:
    def __init__(self, settings: EmbeddingSettings) -> None:
        self._api_base = settings.api_base.rstrip("/")
        self._api_key = settings.api_key
        self._model = settings.model
        self._dimensions = settings.dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        started_at = perf_counter()

        wide_event: dict[str, object] = {
            "event": "embed_texts",
            "model": self._model,
            "batch_size": len(texts),
        }

        try:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            payload = {
                "model": self._model,
                "input": texts,
                "dimensions": self._dimensions,
            }

            response = httpx.post(
                f"{self._api_base}/embeddings",
                json=payload,
                headers=headers,
                timeout=EMBEDDING_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()

            data = response.json()
            result = [item["embedding"] for item in data["data"]]
            wide_event["embedding_count"] = len(result)
            wide_event["outcome"] = "success"
            return result
        except Exception as exc:
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            raise
        finally:
            wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            logger.info("embed_texts", extra={"wide_event": wide_event})
