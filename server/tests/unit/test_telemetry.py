from __future__ import annotations

from fastapi import FastAPI

from typing import Any

from app.core.config import (
    AppSettings,
    CohereSettings,
    DatabaseSettings,
    EmbeddingSettings,
    LLMSettings,
    LogSettings,
    OtelSettings,
    QdrantSettings,
    RedisSettings,
    Settings,
)


def test_configure_telemetry_instruments_app_when_enabled(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeProvider:
        def __init__(self, *, resource) -> None:
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
        log=LogSettings(level="INFO", format="json"),
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
        cohere=CohereSettings(
            api_key=None,
            rerank_model="rerank-english-v3.0",
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
    assert captured["exporter_kwargs"]["endpoint"] == "http://collector:4317"
    assert captured["exporter_kwargs"]["headers"] == {"authorization": "token"}
