from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
import logging
from time import perf_counter

from fastapi import FastAPI
from opentelemetry import metrics, propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter as HttpOTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter as HttpOTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import Settings
from app.core.logging import append_wide_event, get_request_id
from app.core.runtime_context import get_runtime_context

logger = logging.getLogger(__name__)


def inject_job_context() -> dict[str, str]:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    request_id = get_request_id()
    if request_id:
        carrier["x-request-id"] = request_id
    return carrier


def record_degradation(stage: str, **details: object) -> None:
    degradation = {"stage": stage, **details}
    append_wide_event("degradations", degradation)

    span = trace.get_current_span()
    if span.is_recording():
        attributes = {
            f"evidentrag.degradation.{key}": value
            for key, value in degradation.items()
            if isinstance(value, (bool, int, float, str))
        }
        span.add_event("evidentrag.degradation", attributes=attributes)


@contextmanager
def traced_operation(name: str, **attributes: object) -> Iterator[dict[str, object]]:
    started_at = perf_counter()
    operation: dict[str, object] = {"name": name, **attributes}
    span_attributes = {
        f"evidentrag.{key}": value
        for key, value in attributes.items()
        if isinstance(value, (bool, int, float, str))
    }
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(name, attributes=span_attributes):
        try:
            yield operation
            operation.setdefault("outcome", "success")
        except Exception as exc:
            operation["outcome"] = "error"
            operation["error_type"] = type(exc).__name__
            raise
        finally:
            operation["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            append_wide_event("operations", operation)


@dataclass
class TelemetryRuntime:
    app: FastAPI | None
    tracer_provider: TracerProvider
    meter_provider: MeterProvider
    httpx_instrumentor: HTTPXClientInstrumentor
    redis_instrumentor: RedisInstrumentor
    sqlalchemy_instrumentor: SQLAlchemyInstrumentor
    _sqlalchemy_instrumented: bool = field(default=False, init=False)
    _is_shutdown: bool = field(default=False, init=False)

    def instrument_sqlalchemy(self, engine: object) -> None:
        if self._sqlalchemy_instrumented:
            return
        sync_engine = getattr(engine, "sync_engine")
        self.sqlalchemy_instrumentor.instrument(
            engine=sync_engine,
            tracer_provider=self.tracer_provider,
            meter_provider=self.meter_provider,
        )
        self._sqlalchemy_instrumented = True

    def shutdown(self) -> None:
        if self._is_shutdown:
            return
        self._is_shutdown = True

        try:
            if self.app is not None:
                FastAPIInstrumentor.uninstrument_app(self.app)
        finally:
            try:
                self.httpx_instrumentor.uninstrument()
            finally:
                try:
                    if self._sqlalchemy_instrumented:
                        self.sqlalchemy_instrumentor.uninstrument()
                finally:
                    try:
                        self.redis_instrumentor.uninstrument()
                    finally:
                        try:
                            self.meter_provider.force_flush()
                        finally:
                            try:
                                self.meter_provider.shutdown()
                            finally:
                                try:
                                    self.tracer_provider.force_flush()
                                finally:
                                    self.tracer_provider.shutdown()


def configure_telemetry(
    app: FastAPI | None, settings: Settings
) -> TelemetryRuntime | None:
    started_at = perf_counter()
    wide_event: dict[str, object] = {
        "event": "configure_telemetry",
        "enabled": settings.otel.enabled,
    }

    try:
        if not settings.otel.enabled:
            wide_event["outcome"] = "skipped"
            return

        wide_event["protocol"] = settings.otel.exporter_otlp_protocol
        runtime_context = get_runtime_context(settings)
        resource = Resource.create(runtime_context.otel_resource_attributes())
        exporter, metric_exporter = _create_exporters(
            settings.otel.exporter_otlp_protocol
        )
        metric_reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[metric_reader],
            shutdown_on_exit=False,
        )
        provider = TracerProvider(
            resource=resource,
            shutdown_on_exit=False,
            meter_provider=meter_provider,
        )
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        metrics.set_meter_provider(meter_provider)

        httpx_instrumentor = HTTPXClientInstrumentor()
        httpx_instrumentor.instrument(
            tracer_provider=provider,
            meter_provider=meter_provider,
        )
        redis_instrumentor = RedisInstrumentor()
        redis_instrumentor.instrument(tracer_provider=provider)
        sqlalchemy_instrumentor = SQLAlchemyInstrumentor()

        if app is not None:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=provider,
                meter_provider=meter_provider,
                excluded_urls=settings.otel.excluded_urls,
                exclude_spans=["receive", "send"],
            )
        wide_event["outcome"] = "success"
        return TelemetryRuntime(
            app=app,
            tracer_provider=provider,
            meter_provider=meter_provider,
            httpx_instrumentor=httpx_instrumentor,
            redis_instrumentor=redis_instrumentor,
            sqlalchemy_instrumentor=sqlalchemy_instrumentor,
        )
    except Exception as exc:
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        log = logger.error if wide_event.get("outcome") == "error" else logger.info
        log("configure_telemetry", extra={"wide_event": wide_event})


def _create_exporters(protocol: str):
    if protocol == "grpc":
        return OTLPSpanExporter(), OTLPMetricExporter()
    if protocol == "http/protobuf":
        return HttpOTLPSpanExporter(), HttpOTLPMetricExporter()
    raise ValueError(f"Unsupported OTLP protocol: {protocol}")
