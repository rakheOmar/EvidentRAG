from __future__ import annotations

import logging
from time import perf_counter

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import Settings

logger = logging.getLogger(__name__)


def configure_telemetry(app: FastAPI, settings: Settings) -> None:
    started_at = perf_counter()
    wide_event: dict[str, object] = {"event": "configure_telemetry"}

    try:
        if not settings.otel.enabled:
            wide_event["outcome"] = "skipped"
            return

        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.otel.service_name,
                    "deployment.environment": settings.app.environment,
                }
            )
        )
        exporter = OTLPSpanExporter(
            endpoint=settings.otel.exporter_otlp_endpoint,
            headers=_parse_headers(settings.otel.exporter_otlp_headers),
            insecure=(settings.otel.exporter_otlp_protocol == "grpc"),
        )
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls=settings.otel.excluded_urls,
        )
        wide_event["outcome"] = "success"
    except Exception as exc:
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        logger.info("configure_telemetry", extra={"wide_event": wide_event})


def _parse_headers(headers: str | None) -> dict[str, str] | None:
    if not headers:
        return None

    parsed_headers: dict[str, str] = {}
    for item in headers.split(","):
        key, _, value = item.partition("=")
        if key and value:
            parsed_headers[key.strip()] = value.strip()
    return parsed_headers or None
