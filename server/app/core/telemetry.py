from __future__ import annotations

import logging

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
    if not settings.otel_enabled:
        logger.info("telemetry_disabled")
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.otel_service_name,
                "deployment.environment": settings.environment,
            }
        )
    )
    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        headers=_parse_headers(settings.otel_exporter_otlp_headers),
        insecure=(settings.otel_exporter_otlp_protocol == "grpc"),
    )
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls=settings.otel_excluded_urls,
    )
    logger.info("telemetry_configured")


def _parse_headers(headers: str | None) -> dict[str, str] | None:
    if not headers:
        return None

    parsed_headers: dict[str, str] = {}
    for item in headers.split(","):
        key, _, value = item.partition("=")
        if key and value:
            parsed_headers[key.strip()] = value.strip()
    return parsed_headers or None
