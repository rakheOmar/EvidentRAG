from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.logging import enrich_wide_event, get_request_id
from tests.support.runtime_fakes import ApplicationRuntimeHarness


def _runtime_context(**pipeline_dependencies: object) -> dict[str, object]:
    return {
        "session_factory": object(),
        "redis": object(),
        "embedding_client": object(),
        "qdrant_store": object(),
        "llm_client": object(),
        **pipeline_dependencies,
    }


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

    ctx = _runtime_context(rerank_client=object(), arag_router=object())

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
    ctx = _runtime_context(rerank_client=object(), arag_router=object())

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

    ctx = _runtime_context(rerank_client=object(), arag_router=object())

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
    ctx = _runtime_context(document_storage=object())
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

    runtime = ApplicationRuntimeHarness(qdrant_degradation=True)
    runtime.patch_worker(monkeypatch, worker_module)
    log_records: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        worker_module.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )

    ctx: dict[str, object] = {}

    await worker_module.startup(ctx)

    assert runtime.created_db_settings is runtime.settings.db
    assert runtime.session_engine is runtime.engine
    assert runtime.qdrant_store is not None
    assert runtime.qdrant_store.settings is runtime.settings.qdrant
    assert runtime.qdrant_store.collection_ensured is True
    assert runtime.embedding_client is not None
    assert runtime.embedding_client.settings is runtime.settings.embeddings
    assert runtime.llm_client is not None
    assert runtime.llm_client.settings is runtime.settings.llm
    assert runtime.llm_client.list_models_calls == 1
    assert runtime.llm_client.catalog == ["model-test"]
    assert runtime.rerank_client is not None
    assert runtime.rerank_client.settings is runtime.settings.reranker
    assert runtime.redis_url == runtime.settings.redis.url
    assert runtime.arag_router is not None
    assert runtime.arag_router.llm_client is runtime.llm_client
    assert runtime.telemetry_app is None
    assert runtime.telemetry_settings is runtime.settings
    assert runtime.telemetry.instrumented_engine is runtime.engine
    assert runtime.embedding_client.scheduler is runtime.llm_client.scheduler
    assert runtime.embedding_client.scheduler is runtime.rerank_client.scheduler

    document_storage = ctx.pop("document_storage")
    assert document_storage.__class__.__name__ == "LocalDocumentStorage"
    assert ctx == {
        "engine": runtime.engine,
        "session_factory": runtime.session_factory,
        "qdrant_store": runtime.qdrant_store,
        "embedding_client": runtime.embedding_client,
        "llm_client": runtime.llm_client,
        "rerank_client": runtime.rerank_client,
        "redis": runtime.redis,
        "arag_router": runtime.arag_router,
        "telemetry": runtime.telemetry,
    }
    startup_records = [
        record for record in log_records if record[0] == "worker_startup"
    ]
    assert len(startup_records) == 1
    startup_event = startup_records[0][1]["extra"]["wide_event"]
    assert "model_catalog" not in startup_event
    assert startup_event["degradations"] == [
        {"stage": "qdrant_payload_index", "field": "source_id"}
    ]


@pytest.mark.asyncio
async def test_worker_startup_records_model_catalog_degradation(monkeypatch) -> None:
    from app import worker as worker_module

    runtime = ApplicationRuntimeHarness(
        model_catalog_error=RuntimeError("model service unavailable")
    )
    runtime.patch_worker(monkeypatch, worker_module)
    log_records: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        worker_module.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )

    await worker_module.startup({})

    assert runtime.llm_client is not None
    assert runtime.llm_client.list_models_calls == 1
    assert runtime.llm_client.catalog is None
    startup_records = [
        record for record in log_records if record[0] == "worker_startup"
    ]
    assert len(startup_records) == 1
    assert startup_records[0][1]["extra"]["wide_event"]["model_catalog"] == {
        "outcome": "degraded",
        "error_type": "RuntimeError",
        "error_message": "model service unavailable",
    }


@pytest.mark.asyncio
async def test_worker_shutdown_closes_redis_and_disposes_engine() -> None:
    from app import worker as worker_module

    runtime = ApplicationRuntimeHarness()
    ctx = {
        "redis": runtime.redis,
        "engine": runtime.engine,
        "telemetry": runtime.telemetry,
    }

    await worker_module.shutdown(ctx)

    assert runtime.redis.closed is True
    assert runtime.engine.disposed is True
    assert runtime.telemetry.shutdown_calls == 1
    assert runtime.lifecycle == [
        "redis_closed",
        "engine_disposed",
        "telemetry_shutdown",
    ]


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
