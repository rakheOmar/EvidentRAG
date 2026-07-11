from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.core.config import (
    AppSettings,
    DatabaseSettings,
    EmbeddingSettings,
    LLMSettings,
    LogSettings,
    OtelSettings,
    QdrantSettings,
    RedisSettings,
    RerankerSettings,
    Settings,
)


@pytest.mark.asyncio
async def test_run_message_pipeline_builds_pipeline_from_ctx_and_runs_message(
    monkeypatch,
) -> None:
    from app import worker as worker_module

    captured: dict[str, object] = {}
    message_id = uuid.uuid4()

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
            arag_router,
        ) -> None:
            captured["init_kwargs"] = {
                "session_factory": session_factory,
                "redis": redis,
                "embedding_client": embedding_client,
                "qdrant_store": qdrant_store,
                "rerank_client": rerank_client,
                "llm_client": llm_client,
                "arag_router": arag_router,
            }

        async def run(self, actual_message_id) -> None:
            captured["message_id"] = actual_message_id

    monkeypatch.setattr(worker_module, "QueryPipeline", FakeQueryPipeline)

    ctx = {
        "session_factory": object(),
        "redis": object(),
        "embedding_client": object(),
        "qdrant_store": object(),
        "rerank_client": object(),
        "llm_client": object(),
        "arag_router": object(),
    }

    await worker_module.run_message_pipeline(ctx, message_id)

    assert captured["init_kwargs"] == ctx
    assert captured["message_id"] == message_id


@pytest.mark.asyncio
async def test_run_message_pipeline_skips_non_retryable_errors(monkeypatch) -> None:
    from app.application.query_pipeline.query_pipeline import NonRetryablePipelineError
    from app import worker as worker_module

    class FakeQueryPipeline:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def run(self, actual_message_id) -> None:
            raise NonRetryablePipelineError(
                f"Assistant message not found: {actual_message_id}"
            )

    monkeypatch.setattr(worker_module, "QueryPipeline", FakeQueryPipeline)

    ctx = {
        "session_factory": object(),
        "redis": object(),
        "embedding_client": object(),
        "qdrant_store": object(),
        "rerank_client": object(),
        "llm_client": object(),
        "arag_router": object(),
    }

    await worker_module.run_message_pipeline(ctx, uuid.uuid4())


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
        reranker=RerankerSettings(
            api_base="https://api.cohere.com/v2",
            api_key=None,
            model="rerank-english-v3.0",
        ),
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
        def __init__(self, actual_settings, scheduler=None) -> None:
            captured["llm_settings"] = actual_settings
            captured["llm_client_instance"] = self

    class FakeAragRouter:
        def __init__(self, llm_client) -> None:
            captured["arag_router_llm_client"] = llm_client
            captured["arag_router_instance"] = self

    class FakeRerankClient:
        def __init__(self, actual_settings, scheduler=None) -> None:
            captured["reranker_settings"] = actual_settings
            captured["rerank_client_instance"] = self

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
    monkeypatch.setattr(worker_module, "AragRouter", FakeAragRouter)
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
    assert captured["reranker_settings"] is settings.reranker
    assert captured["redis_url"] == settings.redis.url
    assert captured["ensure_collection_called"] is True
    assert captured["arag_router_llm_client"] is captured["llm_client_instance"]

    document_storage = ctx.pop("document_storage")
    assert document_storage.__class__.__name__ == "LocalDocumentStorage"
    assert ctx == {
        "engine": fake_engine,
        "session_factory": fake_session_factory,
        "qdrant_store": captured["qdrant_store_instance"],
        "embedding_client": captured["embedding_client_instance"],
        "llm_client": captured["llm_client_instance"],
        "rerank_client": captured["rerank_client_instance"],
        "redis": fake_redis,
        "arag_router": captured["arag_router_instance"],
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


def test_worker_settings_registers_message_pipeline() -> None:
    from app import worker as worker_module

    assert (
        worker_module.WorkerSettings.functions[0] is worker_module.run_message_pipeline
    )
    document_function = worker_module.WorkerSettings.functions[1]
    assert document_function.name == "run_document_ingestion"
    assert document_function.max_tries == 3
    assert worker_module.WorkerSettings.cron_jobs[0].name == (
        "cron:cleanup_deleted_documents"
    )


@pytest.mark.asyncio
async def test_cleanup_deleted_documents_removes_expired_source_documents(
    monkeypatch,
) -> None:
    from app import worker as worker_module

    source_id = uuid.uuid4()
    document_id = uuid.uuid4()
    source = SimpleNamespace(id=source_id)
    document = SimpleNamespace(
        id=document_id,
        source_id=source_id,
        storage_key="documents/example.pdf",
    )
    deleted_objects: list[object] = []
    qdrant_document_ids: list[str] = []
    storage_keys: list[str] = []
    committed = False

    class FakeScalarResult:
        def __init__(self, values: list[object]) -> None:
            self.values = values

        def __iter__(self):
            return iter(self.values)

    class FakeSession:
        scalars_calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def scalars(self, statement):
            self.scalars_calls += 1
            if self.scalars_calls == 1:
                return FakeScalarResult([source])
            return FakeScalarResult([document])

        async def delete(self, item) -> None:
            deleted_objects.append(item)

        async def commit(self) -> None:
            nonlocal committed
            committed = True

    class FakeSessionFactory:
        def __call__(self):
            return FakeSession()

    class FakeQdrantStore:
        async def delete_document_points(self, actual_document_id: str) -> None:
            qdrant_document_ids.append(actual_document_id)

    class FakeStorage:
        def delete(self, storage_key: str) -> None:
            storage_keys.append(storage_key)

    test_settings = SimpleNamespace(
        ingestion=SimpleNamespace(audit_retention_days=7),
    )
    monkeypatch.setattr(worker_module, "settings", test_settings)

    await worker_module.cleanup_deleted_documents(
        {
            "session_factory": FakeSessionFactory(),
            "qdrant_store": FakeQdrantStore(),
            "document_storage": FakeStorage(),
        }
    )

    assert qdrant_document_ids == [str(document_id)]
    assert storage_keys == ["documents/example.pdf"]
    assert deleted_objects == [document, source]
    assert committed is True
