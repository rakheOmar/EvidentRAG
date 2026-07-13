from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

import app.main as main_module
from tests.support.runtime_fakes import ApplicationRuntimeHarness
from tests.support.settings import build_runtime_settings


app = main_module.app


def test_startup_initializes_runtime_seeds_and_cleans_up(monkeypatch) -> None:
    runtime = ApplicationRuntimeHarness(
        settings=build_runtime_settings(seed_demo_data=True),
        qdrant_degradation=True,
    )
    runtime.patch_main(monkeypatch, main_module)
    seed_calls: list[dict[str, object]] = []
    log_records: list[tuple[str, dict[str, Any]]] = []

    async def fake_seed_demo_data(**kwargs: object) -> int:
        seed_calls.append(kwargs)
        return 1

    monkeypatch.setattr(main_module, "seed_demo_data", fake_seed_demo_data)
    monkeypatch.setattr(
        main_module.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )
    app.state.telemetry = runtime.telemetry

    with TestClient(app):
        assert app.state.session_factory is runtime.session_factory
        assert app.state.qdrant_store is runtime.qdrant_store
        assert app.state.embedding_client is runtime.embedding_client
        assert app.state.llm_client is runtime.llm_client
        assert app.state.rerank_client is runtime.rerank_client
        assert app.state.redis is runtime.redis
        assert app.state.job_queue is runtime.job_queue
        assert app.state.model_catalog == ["model-test"]

    assert runtime.created_db_settings is runtime.settings.db
    assert runtime.session_engine is runtime.engine
    assert runtime.telemetry.instrumented_engine is runtime.engine
    assert runtime.engine_begin_calls == 1
    assert runtime.schema_callback == main_module.Base.metadata.create_all
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
    assert runtime.embedding_client.scheduler is runtime.llm_client.scheduler
    assert runtime.embedding_client.scheduler is runtime.rerank_client.scheduler
    assert runtime.redis_url == runtime.settings.redis.url
    assert runtime.job_queue_url == runtime.settings.redis.url
    assert seed_calls == [
        {
            "session_factory": runtime.session_factory,
            "qdrant_store": runtime.qdrant_store,
            "embedding_client": runtime.embedding_client,
        }
    ]
    assert runtime.lifecycle == [
        "job_queue_closed",
        "redis_closed",
        "engine_disposed",
        "telemetry_shutdown",
    ]

    startup_records = [record for record in log_records if record[0] == "app_startup"]
    assert len(startup_records) == 1
    startup_event = startup_records[0][1]["extra"]["wide_event"]
    assert startup_event["seeded_documents"] == 1
    assert startup_event["degradations"] == [
        {"stage": "qdrant_payload_index", "field": "source_id"}
    ]
    assert "seed_demo_data_starting" not in [message for message, _ in log_records]


def test_startup_skips_demo_seeding_when_disabled(monkeypatch) -> None:
    runtime = ApplicationRuntimeHarness(
        settings=build_runtime_settings(seed_demo_data=False)
    )
    runtime.patch_main(monkeypatch, main_module)

    async def fail_if_called(**kwargs: object) -> int:
        raise AssertionError("seed_demo_data should not be called")

    monkeypatch.setattr(main_module, "seed_demo_data", fail_if_called)
    app.state.telemetry = None

    with TestClient(app):
        assert app.state.session_factory is runtime.session_factory
        assert app.state.job_queue is runtime.job_queue
        assert app.state.embedding_client is runtime.embedding_client
        assert app.state.llm_client is runtime.llm_client
        assert app.state.rerank_client is runtime.rerank_client

    assert runtime.engine_begin_calls == 1
    assert runtime.schema_callback == main_module.Base.metadata.create_all
    assert runtime.qdrant_store is not None
    assert runtime.qdrant_store.collection_ensured is True
    assert runtime.llm_client is not None
    assert runtime.llm_client.catalog == ["model-test"]
    assert runtime.lifecycle == [
        "job_queue_closed",
        "redis_closed",
        "engine_disposed",
    ]


def test_startup_records_model_catalog_degradation_and_continues(monkeypatch) -> None:
    runtime = ApplicationRuntimeHarness(
        model_catalog_error=RuntimeError("model service unavailable")
    )
    runtime.patch_main(monkeypatch, main_module)
    log_records: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        main_module.logger,
        "info",
        lambda message, **kwargs: log_records.append((message, kwargs)),
    )
    app.state.telemetry = None

    with TestClient(app):
        assert app.state.model_catalog == []
        assert app.state.llm_client is runtime.llm_client

    assert runtime.llm_client is not None
    assert runtime.llm_client.list_models_calls == 1
    assert runtime.llm_client.catalog == []
    startup_records = [record for record in log_records if record[0] == "app_startup"]
    assert len(startup_records) == 1
    assert startup_records[0][1]["extra"]["wide_event"]["model_catalog"] == {
        "outcome": "degraded",
        "error_type": "RuntimeError",
        "error_message": "model service unavailable",
    }
