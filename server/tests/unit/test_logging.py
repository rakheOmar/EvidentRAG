from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.logging import ContextFilter, JsonFormatter, configure_logging


def test_context_filter_adds_shared_deployment_context(monkeypatch) -> None:
    monkeypatch.setenv("SERVICE_VERSION", "1.2.3")
    monkeypatch.setenv("COMMIT_SHA", "abc123")
    monkeypatch.setenv("SERVICE_INSTANCE_ID", "instance-7")
    monkeypatch.setenv("REGION", "ap-south-1")
    settings = get_settings()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="test_event",
        args=(),
        exc_info=None,
    )

    ContextFilter(settings).filter(record)

    assert getattr(record, "service_name") == settings.otel.service_name
    assert getattr(record, "environment") == settings.app.environment
    assert getattr(record, "version") == "1.2.3"
    assert getattr(record, "commit_hash") == "abc123"
    assert getattr(record, "instance_id") == "instance-7"
    assert getattr(record, "region") == "ap-south-1"


def test_configure_logging_suppresses_duplicate_framework_events() -> None:
    configure_logging(get_settings())

    root_handler = logging.getLogger().handlers[0]
    assert isinstance(root_handler.formatter, JsonFormatter)

    for logger_name in (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "httpx",
        "httpcore",
        "arq",
        "arq.worker",
    ):
        assert logging.getLogger(logger_name).level == logging.ERROR
