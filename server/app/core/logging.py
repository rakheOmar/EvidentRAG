from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import datetime, timezone
import json
import logging
from logging.config import dictConfig

from app.core.config import Settings
from app.core.runtime_context import get_runtime_context

try:
    from opentelemetry import trace
except Exception:  # pragma: no cover - handled when deps are absent
    trace = None


_REQUEST_ID: ContextVar[str | None] = ContextVar("request_id", default=None)
_WIDE_EVENT: ContextVar[dict[str, object] | None] = ContextVar(
    "wide_event", default=None
)


def set_request_id(request_id: str | None) -> Token[str | None]:
    return _REQUEST_ID.set(request_id)


def get_request_id() -> str | None:
    return _REQUEST_ID.get()


def reset_request_id(token: Token[str | None]) -> None:
    _REQUEST_ID.reset(token)


def set_wide_event(
    wide_event: dict[str, object],
) -> Token[dict[str, object] | None]:
    return _WIDE_EVENT.set(wide_event)


def reset_wide_event(token: Token[dict[str, object] | None]) -> None:
    _WIDE_EVENT.reset(token)


def enrich_wide_event(**fields: object) -> None:
    wide_event = _WIDE_EVENT.get()
    if wide_event is not None:
        wide_event.update(fields)


def append_wide_event(field: str, value: object) -> None:
    wide_event = _WIDE_EVENT.get()
    if wide_event is None:
        return
    values = wide_event.setdefault(field, [])
    if isinstance(values, list):
        values.append(value)


class ContextFilter(logging.Filter):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._runtime = get_runtime_context(settings)

    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = getattr(
            record, "service_name", self._runtime.service_name
        )
        record.environment = getattr(record, "environment", self._runtime.environment)
        record.request_id = getattr(record, "request_id", None) or get_request_id()
        record.commit_hash = self._runtime.commit_hash
        record.version = self._runtime.version
        record.instance_id = self._runtime.instance_id
        record.region = self._runtime.region

        trace_id: str | None = getattr(record, "trace_id", None)
        span_id: str | None = getattr(record, "span_id", None)
        if trace is not None and trace_id is None and span_id is None:
            span_context = trace.get_current_span().get_span_context()
            if span_context.is_valid:
                trace_id = format(span_context.trace_id, "032x")
                span_id = format(span_context.span_id, "016x")

        record.trace_id = trace_id
        record.span_id = span_id
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
        }

        wide_event = getattr(record, "wide_event", None)
        if isinstance(wide_event, dict):
            payload.update(wide_event)
        else:
            payload["message"] = record.getMessage()

        for key in (
            "service_name",
            "environment",
            "request_id",
            "trace_id",
            "span_id",
            "commit_hash",
            "version",
            "instance_id",
            "region",
            "http_method",
            "http_path",
            "http_status_code",
            "duration_ms",
        ):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context": {"()": ContextFilter, "settings": settings},
            },
            "formatters": {
                "json": {"()": JsonFormatter},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["context"],
                }
            },
            "loggers": {
                logger_name: {"level": "ERROR", "propagate": True}
                for logger_name in (
                    "uvicorn",
                    "uvicorn.access",
                    "uvicorn.error",
                    "httpx",
                    "httpcore",
                    "arq",
                    "arq.worker",
                )
            },
            "root": {"level": settings.log.level, "handlers": ["default"]},
        }
    )
