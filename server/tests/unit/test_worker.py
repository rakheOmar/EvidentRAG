from __future__ import annotations

import uuid

import pytest

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


@pytest.mark.asyncio
async def test_run_query_pipeline_builds_pipeline_from_ctx_and_runs_query(
    monkeypatch,
) -> None:
    from app import worker as worker_module

    captured: dict[str, object] = {}
    query_id = uuid.uuid4()

    class FakeQueryPipeline:
        def __init__(
            self,
            *,
            session_factory,
            redis,
            embedding_client,
            qdrant_store,
            rerank_client,
            llm_client,
        ) -> None:
            captured["init_kwargs"] = {
                "session_factory": session_factory,
                "redis": redis,
                "embedding_client": embedding_client,
                "qdrant_store": qdrant_store,
                "rerank_client": rerank_client,
                "llm_client": llm_client,
            }

        async def run(self, actual_query_id) -> None:
            captured["query_id"] = actual_query_id

    monkeypatch.setattr(worker_module, "QueryPipeline", FakeQueryPipeline)

    ctx = {
        "session_factory": object(),
        "redis": object(),
        "embedding_client": object(),
        "qdrant_store": object(),
        "rerank_client": object(),
        "llm_client": object(),
    }

    await worker_module.run_query_pipeline(ctx, query_id)

    assert captured["init_kwargs"] == ctx
    assert captured["query_id"] == query_id


@pytest.mark.asyncio
async def test_worker_startup_populates_runtime_dependencies(monkeypatch) -> None:
    from app import worker as worker_module

    captured: dict[str, object] = {}
    fake_engine = object()
    fake_session_factory = object()
    fake_redis = object()

    settings = Settings(
        app=AppSettings(
            app_name="EvidentRAG",
            environment="test",
            client_dist_path="../client/dist",
        ),
        log=LogSettings(level="INFO", format="json"),
        otel=OtelSettings(
            enabled=False,
            service_name="server-test",
            exporter_otlp_endpoint=None,
            exporter_otlp_headers=None,
            exporter_otlp_protocol="grpc",
            excluded_urls="/health",
        ),
        embeddings=EmbeddingSettings(
            api_base="http://embedding.test/v1",
            api_key=None,
            model="embed-test",
            dimensions=768,
            seed_demo_data=False,
        ),
        llm=LLMSettings(
            api_base="http://llm.test/v1",
            api_key=None,
            generation_model="llm-generation-test",
            utility_model="llm-utility-test",
        ),
        cohere=CohereSettings(api_key=None, rerank_model="rerank-english-v3.0"),
        db=DatabaseSettings(
            host="localhost",
            port=5432,
            user="evidentrag",
            password="evidentrag",
            db="evidentrag",
        ),
        qdrant=QdrantSettings(
            url="http://qdrant:6333",
            evidence_collection="evidentrag_evidence",
        ),
        redis=RedisSettings(url="redis://localhost:6379/0"),
    )

    class FakeQdrantStore:
        def __init__(self, actual_settings) -> None:
            captured["qdrant_settings"] = actual_settings
            captured["qdrant_store_instance"] = self

        async def ensure_collection(self) -> None:
            captured["ensure_collection_called"] = True

    class FakeEmbeddingClient:
        def __init__(self, actual_settings) -> None:
            captured["embedding_settings"] = actual_settings
            captured["embedding_client_instance"] = self

    class FakeLLMClient:
        def __init__(self, actual_settings) -> None:
            captured["llm_settings"] = actual_settings
            captured["llm_client_instance"] = self

    class FakeRerankClient:
        def __init__(self, actual_settings) -> None:
            captured["cohere_settings"] = actual_settings
            captured["rerank_client_instance"] = self

    class FakeRedis:
        async def aclose(self) -> None:
            captured["redis_closed"] = True

    def fake_create_engine(actual_settings) -> object:
        captured["db_settings"] = actual_settings
        return fake_engine

    def fake_create_session_factory(actual_engine) -> object:
        captured["session_engine"] = actual_engine
        return fake_session_factory

    def fake_redis_from_url(url: str) -> object:
        captured["redis_url"] = url
        return fake_redis

    monkeypatch.setattr(worker_module, "settings", settings)
    monkeypatch.setattr(worker_module, "create_engine", fake_create_engine)
    monkeypatch.setattr(
        worker_module, "create_session_factory", fake_create_session_factory
    )
    monkeypatch.setattr(worker_module, "QdrantStore", FakeQdrantStore)
    monkeypatch.setattr(worker_module, "EmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(worker_module, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(worker_module, "RerankClient", FakeRerankClient)
    monkeypatch.setattr(
        worker_module.Redis, "from_url", staticmethod(fake_redis_from_url)
    )

    ctx: dict[str, object] = {}

    await worker_module.startup(ctx)

    assert captured["db_settings"] is settings.db
    assert captured["session_engine"] is fake_engine
    assert captured["qdrant_settings"] is settings.qdrant
    assert captured["embedding_settings"] is settings.embeddings
    assert captured["llm_settings"] is settings.llm
    assert captured["cohere_settings"] is settings.cohere
    assert captured["redis_url"] == settings.redis.url
    assert captured["ensure_collection_called"] is True

    assert ctx == {
        "engine": fake_engine,
        "session_factory": fake_session_factory,
        "qdrant_store": captured["qdrant_store_instance"],
        "embedding_client": captured["embedding_client_instance"],
        "llm_client": captured["llm_client_instance"],
        "rerank_client": captured["rerank_client_instance"],
        "redis": fake_redis,
    }


@pytest.mark.asyncio
async def test_worker_shutdown_closes_redis_and_disposes_engine() -> None:
    from app import worker as worker_module

    captured: dict[str, bool] = {
        "redis_closed": False,
        "engine_disposed": False,
    }

    class FakeRedis:
        async def aclose(self) -> None:
            captured["redis_closed"] = True

    class FakeEngine:
        async def dispose(self) -> None:
            captured["engine_disposed"] = True

    ctx = {
        "redis": FakeRedis(),
        "engine": FakeEngine(),
    }

    await worker_module.shutdown(ctx)

    assert captured == {
        "redis_closed": True,
        "engine_disposed": True,
    }


def test_worker_settings_expose_arq_hooks() -> None:
    from app import worker as worker_module

    assert worker_module.WorkerSettings.functions == [worker_module.run_query_pipeline]
    on_startup = worker_module.WorkerSettings.__dict__["on_startup"]
    on_shutdown = worker_module.WorkerSettings.__dict__["on_shutdown"]

    assert isinstance(on_startup, staticmethod)
    assert isinstance(on_shutdown, staticmethod)
    assert on_startup.__func__ is worker_module.startup
    assert on_shutdown.__func__ is worker_module.shutdown
    assert (
        worker_module.WorkerSettings.redis_settings
        == worker_module.RedisSettings.from_dsn(worker_module.settings.redis.url)
    )
