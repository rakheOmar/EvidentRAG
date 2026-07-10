from __future__ import annotations

from fastapi.testclient import TestClient

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
)
from typing import Any

import app.main as main_module


app = main_module.app


def test_startup_seeds_demo_data_when_enabled(monkeypatch) -> None:
    captured: dict[str, Any] = {}
    log_records: list[tuple[str, dict[str, Any]]] = []

    class FakeConnection:
        async def run_sync(self, callback) -> None:
            captured["create_all_callback"] = callback

    class FakeBeginContext:
        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeEngine:
        def begin(self) -> FakeBeginContext:
            captured["begin_called"] = True
            return FakeBeginContext()

        async def dispose(self) -> None:
            pass

    class FakeQdrantStore:
        def __init__(self, settings) -> None:
            captured["qdrant_settings"] = settings

        async def ensure_collection(self) -> None:
            captured["ensure_collection_called"] = True

    class FakeEmbeddingClient:
        def __init__(self, settings) -> None:
            captured["embedding_settings"] = settings

    class FakeLLMClient:
        def __init__(self, settings) -> None:
            captured["llm_settings"] = settings

    class FakeRerankClient:
        def __init__(self, settings) -> None:
            captured["reranker_settings"] = settings

    class FakeJobQueue:
        async def aclose(self) -> None:
            captured["job_queue_closed"] = True

    fake_engine = FakeEngine()
    fake_session_factory = object()
    fake_job_queue = FakeJobQueue()

    settings = Settings(
        app=AppSettings(
            app_name="EvidentRAG",
            environment="development",
            client_dist_path="../client/dist",
        ),
        log=LogSettings(level="INFO", format="json"),
        otel=OtelSettings(
            enabled=False,
            service_name="evidentrag-server",
            exporter_otlp_endpoint=None,
            exporter_otlp_headers=None,
            exporter_otlp_protocol="grpc",
            excluded_urls="/health",
        ),
        embeddings=EmbeddingSettings(
            api_base="http://optiplex-3020:8081/v1",
            api_key=None,
            seed_demo_data=True,
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

    async def fake_seed_demo_data(*, session_factory, qdrant_store, embedding_client):
        captured["seed_args"] = {
            "session_factory": session_factory,
            "qdrant_store": qdrant_store,
            "embedding_client": embedding_client,
        }
        return 1

    def fake_create_engine(db_settings):
        captured["db_settings"] = db_settings
        return fake_engine

    def fake_create_session_factory(engine):
        captured["session_engine"] = engine
        return fake_session_factory

    def fake_configure_telemetry(fastapi_app, actual_settings) -> None:
        captured["telemetry_app"] = fastapi_app
        captured["telemetry_settings"] = actual_settings

    class FakeArqRedis:
        @staticmethod
        def from_url(url: str) -> FakeJobQueue:
            captured["job_queue_url"] = url
            return fake_job_queue

    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "configure_telemetry", fake_configure_telemetry)
    monkeypatch.setattr(main_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(
        main_module, "create_session_factory", fake_create_session_factory
    )
    monkeypatch.setattr(main_module, "QdrantStore", FakeQdrantStore)
    monkeypatch.setattr(main_module, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(main_module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(main_module, "RerankClient", FakeRerankClient)
    monkeypatch.setattr(main_module, "ArqRedis", FakeArqRedis)
    monkeypatch.setattr(main_module, "seed_demo_data", fake_seed_demo_data)
    monkeypatch.setattr(
        main_module.logger,
        "info",
        lambda message, *args, **kwargs: log_records.append((message, kwargs)),
    )

    with TestClient(app):
        pass

    assert captured["telemetry_app"] is app
    assert captured["telemetry_settings"] is settings
    assert captured["db_settings"] is settings.db
    assert captured["begin_called"] is True
    assert captured["create_all_callback"] == main_module.Base.metadata.create_all
    assert captured["session_engine"] is fake_engine
    assert captured["qdrant_settings"] is settings.qdrant
    assert captured["ensure_collection_called"] is True
    assert captured["reranker_settings"] is settings.reranker
    assert captured["job_queue_url"] == settings.redis.url
    assert captured["embedding_settings"] is settings.embeddings
    assert captured["llm_settings"] is settings.llm
    assert captured["seed_args"]["session_factory"] is fake_session_factory
    assert app.state.session_factory is fake_session_factory
    assert app.state.job_queue is fake_job_queue
    assert isinstance(app.state.embedding_client, FakeEmbeddingClient)
    assert isinstance(app.state.llm_client, FakeLLMClient)
    assert isinstance(app.state.rerank_client, FakeRerankClient)
    assert [message for message, _ in log_records[:2]] == [
        "seed_demo_data_starting",
        "app_startup",
    ]
    assert log_records[1][1]["extra"]["wide_event"]["seeded_documents"] == 1


def test_startup_skips_demo_seeding_when_disabled(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeConnection:
        async def run_sync(self, callback) -> None:
            captured["create_all_callback"] = callback

    class FakeBeginContext:
        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    class FakeEngine:
        def begin(self) -> FakeBeginContext:
            captured["begin_called"] = True
            return FakeBeginContext()

        async def dispose(self) -> None:
            pass

    class FakeQdrantStore:
        def __init__(self, settings) -> None:
            captured["qdrant_settings"] = settings

        async def ensure_collection(self) -> None:
            captured["ensure_collection_called"] = True

    class FakeRerankClient:
        def __init__(self, settings) -> None:
            captured["reranker_settings"] = settings

    class FakeJobQueue:
        async def aclose(self) -> None:
            captured["job_queue_closed"] = True

    class FakeEmbeddingClient:
        def __init__(self, settings) -> None:
            captured["embedding_settings"] = settings

    class FakeLLMClient:
        def __init__(self, settings) -> None:
            captured["llm_settings"] = settings

    settings = Settings(
        app=AppSettings(
            app_name="EvidentRAG",
            environment="development",
            client_dist_path="../client/dist",
        ),
        log=LogSettings(level="INFO", format="json"),
        otel=OtelSettings(
            enabled=False,
            service_name="evidentrag-server",
            exporter_otlp_endpoint=None,
            exporter_otlp_headers=None,
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
    fake_job_queue = FakeJobQueue()

    def fake_create_engine(db_settings):
        captured["db_settings"] = db_settings
        return FakeEngine()

    def fake_create_session_factory(engine):
        captured["session_engine"] = engine
        return object()

    async def fail_if_called(**kwargs):
        raise AssertionError("seed_demo_data should not be called")

    class FakeArqRedis:
        @staticmethod
        def from_url(url: str) -> FakeJobQueue:
            captured["job_queue_url"] = url
            return fake_job_queue

    monkeypatch.setattr(main_module, "settings", settings)
    monkeypatch.setattr(main_module, "configure_telemetry", lambda *args: None)
    monkeypatch.setattr(main_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(
        main_module, "create_session_factory", fake_create_session_factory
    )
    monkeypatch.setattr(main_module, "QdrantStore", FakeQdrantStore)
    monkeypatch.setattr(main_module, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(main_module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(main_module, "RerankClient", FakeRerankClient)
    monkeypatch.setattr(main_module, "ArqRedis", FakeArqRedis)
    monkeypatch.setattr(main_module, "seed_demo_data", fail_if_called)

    with TestClient(app):
        pass

    assert captured["db_settings"] is settings.db
    assert captured["begin_called"] is True
    assert captured["create_all_callback"] == main_module.Base.metadata.create_all
    assert captured["qdrant_settings"] is settings.qdrant
    assert captured["ensure_collection_called"] is True
    assert captured["reranker_settings"] is settings.reranker
    assert captured["job_queue_url"] == settings.redis.url
    assert captured["embedding_settings"] is settings.embeddings
    assert captured["llm_settings"] is settings.llm
    assert app.state.job_queue is fake_job_queue
    assert isinstance(app.state.embedding_client, FakeEmbeddingClient)
    assert isinstance(app.state.llm_client, FakeLLMClient)
    assert isinstance(app.state.rerank_client, FakeRerankClient)
