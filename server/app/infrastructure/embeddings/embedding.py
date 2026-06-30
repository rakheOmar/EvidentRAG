from __future__ import annotations

import httpx

from app.core.config import EmbeddingSettings


EMBEDDING_REQUEST_TIMEOUT_SECONDS = 120.0


class EmbeddingClient:
    def __init__(self, settings: EmbeddingSettings) -> None:
        self._api_base = settings.api_base.rstrip("/")
        self._api_key = settings.api_key
        self._model = settings.model
        self._dimensions = settings.dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
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
        return [item["embedding"] for item in data["data"]]
