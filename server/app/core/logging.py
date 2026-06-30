from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
from logging.config import dictConfig
import sys

from app.core.config import Settings

try:
    from opentelemetry import trace
except Exception:  # pragma: no cover - handled when deps are absent
    trace = None


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()


def clear_request_id() -> None:
    _request_id.set(None)


class ContextFilter(logging.Filter):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._service_name = settings.otel_service_name
        self._environment = settings.environment

    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = getattr(record, "service_name", self._service_name)
        record.environment = getattr(record, "environment", self._environment)
        record.request_id = getattr(record, "request_id", None) or get_request_id()

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
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service_name": getattr(record, "service_name", None),
            "environment": getattr(record, "environment", None),
            "request_id": getattr(record, "request_id", None),
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
        }
        for key in (
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


class PrettyFormatter(logging.Formatter):
    _RESET = "\x1b[0m"
    _DIM = "\x1b[2m"
    _COLORS = {
        "DEBUG": "\x1b[36m",
        "INFO": "\x1b[32m",
        "WARNING": "\x1b[33m",
        "ERROR": "\x1b[31m",
        "CRITICAL": "\x1b[35m",
    }

    def __init__(self) -> None:
        super().__init__(datefmt="%H:%M:%S")
        self._use_color = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime(self.datefmt)
        level = record.levelname.ljust(8)
        logger_name = record.name
        message = record.getMessage()

        if self._use_color:
            level = f"{self._COLORS.get(record.levelname, '')}{level}{self._RESET}"
            timestamp = f"{self._DIM}{timestamp}{self._RESET}"
            logger_name = f"{self._DIM}{logger_name}{self._RESET}"

        line = f"{timestamp} {level} {logger_name} {message}"
        if record.exc_info:
            return f"{line}\n{self.formatException(record.exc_info)}"
        return line


def configure_logging(settings: Settings) -> None:
    formatter_name = "json" if settings.log_format == "json" else "pretty"
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context": {"()": ContextFilter, "settings": settings},
            },
            "formatters": {
                "json": {"()": JsonFormatter},
                "pretty": {"()": PrettyFormatter},
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": formatter_name,
                    "filters": ["context"],
                }
            },
            "root": {"level": settings.log_level, "handlers": ["default"]},
        }
    )
