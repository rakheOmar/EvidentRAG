from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from fastapi import FastAPI

from typing import Any

from app.core.config import (
    AppSettings,
    RerankerSettings,
    DatabaseSettings,
    EmbeddingSettings,
    LLMSettings,
    LogSettings,
    OtelSettings,
    QdrantSettings,
    RedisSettings,
    Settings,
    get_settings,
)
from app.core.logging import reset_request_id, set_request_id


def _patch_noop_metric_dependencies(monkeypatch) -> None:
    class FakeMeterProvider:
        def __init__(self, **kwargs) -> None:
            pass

        def force_flush(self) -> bool:
            return True

        def shutdown(self) -> None:
            pass

    class FakeHttpxInstrumentor:
        def instrument(self, **kwargs) -> None:
            pass

        def uninstrument(self) -> None:
            pass

    class FakeRedisInstrumentor(FakeHttpxInstrumentor):
        pass

    class FakeSqlAlchemyInstrumentor(FakeHttpxInstrumentor):
        pass

    monkeypatch.setattr(
        "app.core.telemetry.OTLPMetricExporter", lambda: object(), raising=False
    )
    monkeypatch.setattr(
        "app.core.telemetry.HttpOTLPMetricExporter", lambda: object(), raising=False
    )
    monkeypatch.setattr(
        "app.core.telemetry.PeriodicExportingMetricReader",
        lambda exporter: object(),
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.telemetry.MeterProvider", FakeMeterProvider, raising=False
    )
    monkeypatch.setattr(
        "app.core.telemetry.HTTPXClientInstrumentor",
        FakeHttpxInstrumentor,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.telemetry.RedisInstrumentor",
        FakeRedisInstrumentor,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.telemetry.SQLAlchemyInstrumentor",
        FakeSqlAlchemyInstrumentor,
        raising=False,
    )
    monkeypatch.setattr(
        "app.core.telemetry.metrics.set_meter_provider",
        lambda provider: None,
        raising=False,
    )


def test_configure_telemetry_uses_standard_exporter_configuration(monkeypatch) -> None:
    _patch_noop_metric_dependencies(monkeypatch)
    captured: dict[str, Any] = {}

    class FakeProvider:
        def __init__(self, *, resource, **kwargs) -> None:
            captured["resource"] = resource

        def add_span_processor(self, processor) -> None:
            captured["processor"] = processor

    class FakeExporter:
        def __init__(self, **kwargs) -> None:
            captured["exporter_kwargs"] = kwargs

    class FakeBatchProcessor:
        def __init__(self, exporter) -> None:
            captured["batch_exporter"] = exporter

    def fake_instrument_app(app: FastAPI, **kwargs) -> None:
        captured["instrumented_app"] = app
        captured["instrument_kwargs"] = kwargs

    def fake_set_tracer_provider(provider) -> None:
        captured["provider"] = provider

    monkeypatch.setattr("app.core.telemetry.TracerProvider", FakeProvider)
    monkeypatch.setattr("app.core.telemetry.OTLPSpanExporter", FakeExporter)
    monkeypatch.setattr("app.core.telemetry.BatchSpanProcessor", FakeBatchProcessor)
    monkeypatch.setattr(
        "app.core.telemetry.FastAPIInstrumentor.instrument_app", fake_instrument_app
    )
    monkeypatch.setattr(
        "app.core.telemetry.trace.set_tracer_provider", fake_set_tracer_provider
    )

    from app.core.telemetry import configure_telemetry

    app = FastAPI()
    settings = Settings(
        app=AppSettings(
            app_name="EvidentRAG",
            environment="development",
            client_dist_path="../client/dist",
        ),
        log=LogSettings(level="INFO"),
        otel=OtelSettings(
            enabled=True,
            service_name="evidentrag-server",
            exporter_otlp_endpoint="http://collector:4317",
            exporter_otlp_headers="authorization=token",
            exporter_otlp_protocol="grpc",
            excluded_urls="/health",
        ),
        embeddings=EmbeddingSettings(
            api_base="http://optiplex-3020:8081/v1",
            api_key=None,
            seed_demo_data=False,
            model="google/gemini-embedding-2",
            dimensions=768,
        ),
        llm=LLMSettings(
            api_base="http://optiplex-3020:8081/v1",
            api_key=None,
            generation_model="gemini-2.5-pro",
            utility_model="gemini-2.5-flash",
        ),
        reranker=RerankerSettings(
            api_base="https://api.cohere.com/v2",
            api_key=None,
            model="rerank-english-v3.0",
        ),
        db=DatabaseSettings(
            host="localhost",
            port=5432,
            user="evidentrag",
            password=None,
            db="evidentrag",
        ),
        qdrant=QdrantSettings(
            url="http://localhost:6333",
            evidence_collection="evidentrag_evidence",
        ),
        redis=RedisSettings(url="redis://localhost:6379/0"),
    )

    configure_telemetry(app, settings)

    assert captured["instrumented_app"] is app
    assert captured["instrument_kwargs"]["excluded_urls"] == "/health"
    assert captured["exporter_kwargs"] == {}


def test_configure_telemetry_emits_one_success_event(monkeypatch) -> None:
    _patch_noop_metric_dependencies(monkeypatch)
    import app.core.telemetry as telemetry

    log_records: list[tuple[str, dict[str, Any]]] = []

    class FakeProvider:
        def __init__(self, **kwargs) -> None:
            pass

        def add_span_processor(self, processor) -> None:
            pass

    monkeypatch.setattr(telemetry, "TracerProvider", FakeProvider)
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", lambda: object())
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", lambda exporter: object())
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(
        telemetry.FastAPIInstrumentor, "instrument_app", lambda app, **kwargs: None
    )
    monkeypatch.setattr(
        telemetry.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )
    settings = get_settings()
    settings = replace(settings, otel=replace(settings.otel, enabled=True))

    telemetry.configure_telemetry(FastAPI(), settings)

    assert len(log_records) == 1
    assert log_records[0][0] == "configure_telemetry"
    event = log_records[0][1]["extra"]["wide_event"]
    assert event["outcome"] == "success"
    assert event["protocol"] == settings.otel.exporter_otlp_protocol
    assert isinstance(event["duration_ms"], float)


def test_configure_telemetry_emits_one_skipped_event(monkeypatch) -> None:
    import app.core.telemetry as telemetry

    log_records: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        telemetry.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )
    settings = get_settings()
    settings = replace(settings, otel=replace(settings.otel, enabled=False))

    assert telemetry.configure_telemetry(FastAPI(), settings) is None

    assert len(log_records) == 1
    assert log_records[0][0] == "configure_telemetry"
    assert log_records[0][1]["extra"]["wide_event"]["outcome"] == "skipped"


def test_configure_telemetry_selects_http_protobuf_exporter(monkeypatch) -> None:
    _patch_noop_metric_dependencies(monkeypatch)
    import app.core.telemetry as telemetry

    selected_exporters: list[str] = []

    class FakeGrpcExporter:
        def __init__(self) -> None:
            selected_exporters.append("grpc")

    class FakeHttpExporter:
        def __init__(self) -> None:
            selected_exporters.append("http/protobuf")

    class FakeProvider:
        def __init__(self, *, resource, **kwargs) -> None:
            pass

        def add_span_processor(self, processor) -> None:
            pass

    monkeypatch.setattr(telemetry, "OTLPSpanExporter", FakeGrpcExporter)
    monkeypatch.setattr(
        telemetry, "HttpOTLPSpanExporter", FakeHttpExporter, raising=False
    )
    monkeypatch.setattr(telemetry, "TracerProvider", FakeProvider)
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", lambda exporter: object())
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(
        telemetry.FastAPIInstrumentor, "instrument_app", lambda app, **kwargs: None
    )

    settings = get_settings()
    settings = replace(
        settings,
        otel=replace(
            settings.otel,
            enabled=True,
            exporter_otlp_protocol="http/protobuf",
        ),
    )

    telemetry.configure_telemetry(FastAPI(), settings)

    assert selected_exporters == ["http/protobuf"]


def test_telemetry_runtime_flushes_and_shuts_down_once(monkeypatch) -> None:
    _patch_noop_metric_dependencies(monkeypatch)
    import app.core.telemetry as telemetry

    lifecycle_calls: list[str] = []

    class FakeProvider:
        def __init__(self, *, resource, **kwargs) -> None:
            pass

        def add_span_processor(self, processor) -> None:
            pass

        def force_flush(self) -> bool:
            lifecycle_calls.append("force_flush")
            return True

        def shutdown(self) -> None:
            lifecycle_calls.append("shutdown")

    monkeypatch.setattr(telemetry, "TracerProvider", FakeProvider)
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", lambda: object())
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", lambda exporter: object())
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(
        telemetry.FastAPIInstrumentor, "instrument_app", lambda app, **kwargs: None
    )
    monkeypatch.setattr(
        telemetry.FastAPIInstrumentor,
        "uninstrument_app",
        lambda app: lifecycle_calls.append("uninstrument_app"),
    )

    settings = get_settings()
    settings = replace(settings, otel=replace(settings.otel, enabled=True))
    runtime = telemetry.configure_telemetry(FastAPI(), settings)

    assert runtime is not None
    runtime.shutdown()
    runtime.shutdown()

    assert lifecycle_calls == ["uninstrument_app", "force_flush", "shutdown"]


def test_configure_telemetry_instruments_fastapi_and_httpx_with_metrics(
    monkeypatch,
) -> None:
    import app.core.telemetry as telemetry

    captured: dict[str, Any] = {}
    lifecycle_calls: list[str] = []

    class FakeMeterProvider:
        def __init__(self, **kwargs) -> None:
            captured["meter_provider_kwargs"] = kwargs

        def force_flush(self) -> bool:
            lifecycle_calls.append("meter_force_flush")
            return True

        def shutdown(self) -> None:
            lifecycle_calls.append("meter_shutdown")

    class FakeTracerProvider:
        def __init__(self, **kwargs) -> None:
            captured["tracer_provider_kwargs"] = kwargs

        def add_span_processor(self, processor) -> None:
            captured["span_processor"] = processor

        def force_flush(self) -> bool:
            lifecycle_calls.append("trace_force_flush")
            return True

        def shutdown(self) -> None:
            lifecycle_calls.append("trace_shutdown")

    class FakeHttpxInstrumentor:
        def instrument(self, **kwargs) -> None:
            captured["httpx_instrument_kwargs"] = kwargs

        def uninstrument(self) -> None:
            lifecycle_calls.append("httpx_uninstrument")

    class FakeRedisInstrumentor:
        def instrument(self, **kwargs) -> None:
            captured["redis_instrument_kwargs"] = kwargs

        def uninstrument(self) -> None:
            lifecycle_calls.append("redis_uninstrument")

    class FakeSqlAlchemyInstrumentor:
        def instrument(self, **kwargs) -> None:
            captured["sqlalchemy_instrument_kwargs"] = kwargs

        def uninstrument(self) -> None:
            lifecycle_calls.append("sqlalchemy_uninstrument")

    def fake_instrument_app(app, **kwargs) -> None:
        captured["fastapi_instrument_kwargs"] = kwargs

    monkeypatch.setattr(telemetry, "OTLPSpanExporter", lambda: object())
    monkeypatch.setattr(
        telemetry, "OTLPMetricExporter", lambda: object(), raising=False
    )
    monkeypatch.setattr(telemetry, "BatchSpanProcessor", lambda exporter: object())
    monkeypatch.setattr(
        telemetry,
        "PeriodicExportingMetricReader",
        lambda exporter: captured.setdefault("metric_reader", object()),
        raising=False,
    )
    monkeypatch.setattr(telemetry, "MeterProvider", FakeMeterProvider, raising=False)
    monkeypatch.setattr(telemetry, "TracerProvider", FakeTracerProvider)
    monkeypatch.setattr(
        telemetry, "HTTPXClientInstrumentor", FakeHttpxInstrumentor, raising=False
    )
    monkeypatch.setattr(
        telemetry, "RedisInstrumentor", FakeRedisInstrumentor, raising=False
    )
    monkeypatch.setattr(
        telemetry,
        "SQLAlchemyInstrumentor",
        FakeSqlAlchemyInstrumentor,
        raising=False,
    )
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(
        telemetry.metrics,
        "set_meter_provider",
        lambda provider: captured.setdefault("global_meter_provider", provider),
        raising=False,
    )
    monkeypatch.setattr(
        telemetry.FastAPIInstrumentor, "instrument_app", fake_instrument_app
    )
    monkeypatch.setattr(
        telemetry.FastAPIInstrumentor,
        "uninstrument_app",
        lambda app: lifecycle_calls.append("fastapi_uninstrument"),
    )

    settings = get_settings()
    settings = replace(settings, otel=replace(settings.otel, enabled=True))
    runtime = telemetry.configure_telemetry(FastAPI(), settings)

    assert runtime is not None
    meter_provider = captured["global_meter_provider"]
    tracer_provider = captured["httpx_instrument_kwargs"]["tracer_provider"]
    assert captured["httpx_instrument_kwargs"]["meter_provider"] is meter_provider
    assert captured["fastapi_instrument_kwargs"] == {
        "tracer_provider": tracer_provider,
        "meter_provider": meter_provider,
        "excluded_urls": settings.otel.excluded_urls,
        "exclude_spans": ["receive", "send"],
    }
    assert captured["redis_instrument_kwargs"] == {
        "tracer_provider": tracer_provider,
    }

    runtime.instrument_sqlalchemy(SimpleNamespace(sync_engine="sync-engine"))

    assert captured["sqlalchemy_instrument_kwargs"] == {
        "engine": "sync-engine",
        "tracer_provider": tracer_provider,
        "meter_provider": meter_provider,
    }

    runtime.shutdown()

    assert lifecycle_calls == [
        "fastapi_uninstrument",
        "httpx_uninstrument",
        "sqlalchemy_uninstrument",
        "redis_uninstrument",
        "meter_force_flush",
        "meter_shutdown",
        "trace_force_flush",
        "trace_shutdown",
    ]


def test_inject_job_context_includes_trace_and_request_id(monkeypatch) -> None:
    import app.core.telemetry as telemetry

    def fake_inject(carrier: dict[str, str]) -> None:
        carrier["traceparent"] = "00-abc-def-01"

    monkeypatch.setattr(telemetry.propagate, "inject", fake_inject, raising=False)
    request_token = set_request_id("request-123")
    try:
        carrier = telemetry.inject_job_context()
    finally:
        reset_request_id(request_token)

    assert carrier == {
        "traceparent": "00-abc-def-01",
        "x-request-id": "request-123",
    }
