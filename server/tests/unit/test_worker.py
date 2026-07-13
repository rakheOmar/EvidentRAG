from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

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
from app.core.logging import enrich_wide_event, get_request_id


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
async def test_run_message_pipeline_preserves_request_context_for_job(
    monkeypatch,
) -> None:
    from app import worker as worker_module

    observed_request_ids: list[str | None] = []
    log_records: list[tuple[str, dict[str, Any]]] = []

    class FakeQueryPipeline:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def run(self, actual_message_id) -> None:
            observed_request_ids.append(get_request_id())
            enrich_wide_event(pipeline={"route": "simple", "retrieval_count": 20})

    monkeypatch.setattr(worker_module, "QueryPipeline", FakeQueryPipeline)
    monkeypatch.setattr(
        worker_module.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )
    ctx = {
        "session_factory": object(),
        "redis": object(),
        "embedding_client": object(),
        "qdrant_store": object(),
        "rerank_client": object(),
        "llm_client": object(),
        "arag_router": object(),
    }

    await worker_module.run_message_pipeline(
        ctx,
        uuid.uuid4(),
        {"x-request-id": "request-123"},
    )

    assert observed_request_ids == ["request-123"]
    assert get_request_id() is None
    records = [record for record in log_records if record[0] == "run_message_pipeline"]
    assert len(records) == 1
    wide_event = records[0][1]["extra"]["wide_event"]
    assert wide_event["request_id"] == "request-123"
    assert wide_event["pipeline"] == {
        "route": "simple",
        "retrieval_count": 20,
    }


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
async def test_run_document_ingestion_preserves_context_and_emits_one_event(
    monkeypatch,
) -> None:
    from app import worker as worker_module

    observed_request_ids: list[str | None] = []
    log_records: list[tuple[str, dict[str, Any]]] = []

    class FakeDocumentIngestionPipeline:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def run(self, document_id: str) -> None:
            observed_request_ids.append(get_request_id())
            enrich_wide_event(document={"id": document_id, "evidence_count": 42})

    monkeypatch.setattr(
        worker_module, "DocumentIngestionPipeline", FakeDocumentIngestionPipeline
    )
    monkeypatch.setattr(
        worker_module.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )
    ctx = {
        "session_factory": object(),
        "redis": object(),
        "embedding_client": object(),
        "llm_client": object(),
        "qdrant_store": object(),
        "document_storage": object(),
    }
    document_id = uuid.uuid4()

    await worker_module.run_document_ingestion(
        ctx,
        document_id,
        {"x-request-id": "request-456"},
    )

    assert observed_request_ids == ["request-456"]
    assert get_request_id() is None
    records = [
        record for record in log_records if record[0] == "run_document_ingestion"
    ]
    assert len(records) == 1
    wide_event = records[0][1]["extra"]["wide_event"]
    assert wide_event["request_id"] == "request-456"
    assert wide_event["document"] == {
        "id": str(document_id),
        "evidence_count": 42,
    }


@pytest.mark.asyncio
async def test_worker_startup_populates_runtime_dependencies(monkeypatch) -> None:
    from app import worker as worker_module

    captured: dict[str, object] = {}
    log_records: list[tuple[str, dict[str, Any]]] = []
    warning_records: list[tuple[str, dict[str, Any]]] = []
    fake_engine = object()
    fake_session_factory = object()
    fake_redis = object()

    class FakeTelemetryRuntime:
        def instrument_sqlalchemy(self, engine) -> None:
            captured["telemetry_engine"] = engine

    fake_telemetry = FakeTelemetryRuntime()

    settings = Settings(
        app=AppSettings(
            app_name="EvidentRAG",
            environment="test",
            client_dist_path="../client/dist",
        ),
        log=LogSettings(level="INFO"),
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
            from app.core.telemetry import record_degradation

            record_degradation("qdrant_payload_index", field="source_id")

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

    def fake_configure_telemetry(app, actual_settings) -> object:
        captured["telemetry_app"] = app
        captured["telemetry_settings"] = actual_settings
        return fake_telemetry

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
        worker_module,
        "configure_telemetry",
        fake_configure_telemetry,
        raising=False,
    )
    monkeypatch.setattr(
        worker_module.Redis, "from_url", staticmethod(fake_redis_from_url)
    )
    monkeypatch.setattr(
        worker_module.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )
    monkeypatch.setattr(
        worker_module.logger,
        "warning",
        lambda message, **kwargs: warning_records.append((message, kwargs)),
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
    assert captured["telemetry_app"] is None
    assert captured["telemetry_settings"] is settings
    assert captured["telemetry_engine"] is fake_engine

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
        "telemetry": fake_telemetry,
    }
    assert warning_records == []
    startup_records = [
        record for record in log_records if record[0] == "worker_startup"
    ]
    assert len(startup_records) == 1
    assert startup_records[0][1]["extra"]["wide_event"]["model_catalog"] == {
        "outcome": "degraded",
        "error_type": "AttributeError",
        "error_message": "'FakeLLMClient' object has no attribute 'set_model_catalog'",
    }
    assert startup_records[0][1]["extra"]["wide_event"]["degradations"] == [
        {"stage": "qdrant_payload_index", "field": "source_id"}
    ]


@pytest.mark.asyncio
async def test_worker_shutdown_closes_redis_and_disposes_engine() -> None:
    from app import worker as worker_module

    captured: dict[str, bool] = {
        "redis_closed": False,
        "engine_disposed": False,
        "telemetry_shutdown": False,
    }

    class FakeRedis:
        async def aclose(self) -> None:
            captured["redis_closed"] = True

    class FakeEngine:
        async def dispose(self) -> None:
            captured["engine_disposed"] = True

    class FakeTelemetryRuntime:
        def shutdown(self) -> None:
            assert captured["redis_closed"] is True
            assert captured["engine_disposed"] is True
            captured["telemetry_shutdown"] = True

    ctx = {
        "redis": FakeRedis(),
        "engine": FakeEngine(),
        "telemetry": FakeTelemetryRuntime(),
    }

    await worker_module.shutdown(ctx)

    assert captured == {
        "redis_closed": True,
        "engine_disposed": True,
        "telemetry_shutdown": True,
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
    observability_call: tuple[str, dict[str, object], object] | None = None

    class FakeJobObservability:
        def __init__(
            self,
            job_name: str,
            identity: dict[str, object],
            trace_context: object,
        ) -> None:
            nonlocal observability_call
            observability_call = (job_name, identity, trace_context)
            self.wide_event = {"event": job_name, **identity}

        def __enter__(self) -> dict[str, object]:
            return self.wide_event

        def __exit__(self, exc_type, exc, traceback) -> None:
            return None

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
    monkeypatch.setattr(worker_module, "_job_observability", FakeJobObservability)

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
    assert observability_call == (
        "deleted_document_cleanup",
        {"retention_days": 7},
        None,
    )
