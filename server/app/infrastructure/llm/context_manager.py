from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil

DEFAULT_CONTEXT_WINDOW = 128_000


@dataclass(frozen=True)
class ContextUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated: bool = True

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class ContextManager:
    """Own current-model context limits and server-side token accounting."""

    def __init__(
        self,
        model_name: str,
        model_catalog: list[dict[str, object]] | None = None,
    ) -> None:
        self.model_name = model_name
        self._context_window = DEFAULT_CONTEXT_WINDOW
        self.set_model_catalog(model_catalog or [])

    @property
    def context_window(self) -> int:
        return self._context_window

    def set_model_catalog(self, model_catalog: list[dict[str, object]]) -> None:
        selected = next(
            (model for model in model_catalog if model.get("id") == self.model_name),
            {},
        )
        for key in (
            "context_window",
            "context_length",
            "max_context_length",
            "max_model_len",
        ):
            value = selected.get(key)
            if isinstance(value, int) and value > 0:
                self._context_window = value
                return

    @staticmethod
    def estimate_tokens(text: str) -> int:
        normalized = text.strip()
        return ceil(len(normalized) / 4) if normalized else 0

    @classmethod
    def _message_text(cls, content: object) -> str:
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""
        return " ".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )

    def prompt_tokens(self, messages: list[dict]) -> int:
        return sum(
            self.estimate_tokens(self._message_text(message.get("content")))
            for message in messages
        )

    def measure(
        self,
        messages: list[dict],
        completion_text: str,
        *,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> ContextUsage:
        prompt = (
            prompt_tokens if prompt_tokens is not None else self.prompt_tokens(messages)
        )
        completion = (
            completion_tokens
            if completion_tokens is not None
            else self.estimate_tokens(completion_text)
        )
        return ContextUsage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            estimated=prompt_tokens is None or completion_tokens is None,
        )
