from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pytest import MonkeyPatch

from app.core.config import Settings
from tests.support.settings import build_runtime_settings


class FakeConnection:
    def __init__(self, runtime: ApplicationRuntimeHarness) -> None:
        self.runtime = runtime

    async def run_sync(self, callback: object) -> None:
        self.runtime.schema_callback = callback


class FakeBeginContext:
    def __init__(self, runtime: ApplicationRuntimeHarness) -> None:
        self.connection = FakeConnection(runtime)

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None


class FakeEngine:
    def __init__(self, runtime: ApplicationRuntimeHarness) -> None:
        self.runtime = runtime
        self.disposed = False

    def begin(self) -> FakeBeginContext:
        self.runtime.engine_begin_calls += 1
        return FakeBeginContext(self.runtime)

    async def dispose(self) -> None:
        self.disposed = True
        self.runtime.lifecycle.append("engine_disposed")


class FakeAsyncResource:
    def __init__(self, runtime: ApplicationRuntimeHarness, name: str) -> None:
        self.runtime = runtime
        self.name = name
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True
        self.runtime.lifecycle.append(f"{self.name}_closed")


class FakeTelemetryRuntime:
    def __init__(self, runtime: ApplicationRuntimeHarness) -> None:
        self.runtime = runtime
        self.instrumented_engine: object | None = None
        self.shutdown_calls = 0

    def instrument_sqlalchemy(self, engine: object) -> None:
        self.instrumented_engine = engine

    def shutdown(self) -> None:
        self.shutdown_calls += 1
        self.runtime.lifecycle.append("telemetry_shutdown")


class FakeQdrantStore:
    def __init__(self, runtime: ApplicationRuntimeHarness, settings: object) -> None:
        self.runtime = runtime
        self.settings = settings
        self.collection_ensured = False
        self.closed = False

    async def ensure_collection(self) -> None:
        self.collection_ensured = True
        if self.runtime.qdrant_degradation:
            from app.core.telemetry import record_degradation

            record_degradation("qdrant_payload_index", field="source_id")

    async def close(self) -> None:
        self.closed = True
        self.runtime.lifecycle.append("qdrant_closed")


class FakeEmbeddingClient:
    def __init__(
        self,
        runtime: ApplicationRuntimeHarness,
        settings: object,
        scheduler: object | None,
    ) -> None:
        self.runtime = runtime
        self.settings = settings
        self.scheduler = scheduler


class FakeLLMClient(FakeEmbeddingClient):
    def __init__(
        self,
        runtime: ApplicationRuntimeHarness,
        settings: object,
        scheduler: object | None,
    ) -> None:
        super().__init__(runtime, settings, scheduler)
        self.catalog: list[str] | None = None
        self.list_models_calls = 0

    async def list_models(self) -> list[str]:
        self.list_models_calls += 1
        if self.runtime.model_catalog_error is not None:
            raise self.runtime.model_catalog_error
        return list(self.runtime.available_models)

    def set_model_catalog(self, models: list[str]) -> None:
        self.catalog = models


class FakeRerankClient(FakeEmbeddingClient):
    pass


class FakeAragRouter:
    def __init__(self, llm_client: object) -> None:
        self.llm_client = llm_client


@dataclass
class ApplicationRuntimeHarness:
    settings: Settings = field(default_factory=build_runtime_settings)
    available_models: list[str] = field(default_factory=lambda: ["model-test"])
    model_catalog_error: Exception | None = None
    qdrant_degradation: bool = False
    lifecycle: list[str] = field(default_factory=list)
    engine_begin_calls: int = 0
    schema_callback: object | None = None
    engine: FakeEngine = field(init=False)
    session_factory: object = field(default_factory=object)
    redis: FakeAsyncResource = field(init=False)
    job_queue: FakeAsyncResource = field(init=False)
    telemetry: FakeTelemetryRuntime = field(init=False)
    qdrant_store: FakeQdrantStore | None = None
    embedding_client: FakeEmbeddingClient | None = None
    llm_client: FakeLLMClient | None = None
    rerank_client: FakeRerankClient | None = None
    arag_router: FakeAragRouter | None = None
    created_db_settings: object | None = None
    session_engine: object | None = None
    redis_url: str | None = None
    job_queue_url: str | None = None
    migration_settings: object | None = None
    telemetry_app: object | None = None
    telemetry_settings: object | None = None

    def __post_init__(self) -> None:
        self.engine = FakeEngine(self)
        self.redis = FakeAsyncResource(self, "redis")
        self.job_queue = FakeAsyncResource(self, "job_queue")
        self.telemetry = FakeTelemetryRuntime(self)

    def create_engine(self, settings: object) -> FakeEngine:
        self.created_db_settings = settings
        return self.engine

    def create_session_factory(self, engine: object) -> object:
        self.session_engine = engine
        return self.session_factory

    def create_qdrant_store(self, settings: object) -> FakeQdrantStore:
        self.qdrant_store = FakeQdrantStore(self, settings)
        return self.qdrant_store

    def create_embedding_client(
        self, settings: object, scheduler: object | None = None
    ) -> FakeEmbeddingClient:
        self.embedding_client = FakeEmbeddingClient(self, settings, scheduler)
        return self.embedding_client

    def create_llm_client(
        self, settings: object, scheduler: object | None = None
    ) -> FakeLLMClient:
        self.llm_client = FakeLLMClient(self, settings, scheduler)
        return self.llm_client

    def create_rerank_client(
        self, settings: object, scheduler: object | None = None
    ) -> FakeRerankClient:
        self.rerank_client = FakeRerankClient(self, settings, scheduler)
        return self.rerank_client

    def create_arag_router(self, *, llm_client: object) -> FakeAragRouter:
        self.arag_router = FakeAragRouter(llm_client)
        return self.arag_router

    def create_redis(self, url: str) -> FakeAsyncResource:
        self.redis_url = url
        return self.redis

    def create_job_queue(self, url: str) -> FakeAsyncResource:
        self.job_queue_url = url
        return self.job_queue

    def upgrade_database(self, settings: object) -> None:
        self.migration_settings = settings

    def configure_telemetry(
        self, app: object | None, settings: object
    ) -> FakeTelemetryRuntime:
        self.telemetry_app = app
        self.telemetry_settings = settings
        return self.telemetry

    def _patch_runtime_dependencies(
        self, monkeypatch: MonkeyPatch, module: Any
    ) -> None:
        monkeypatch.setattr(module, "settings", self.settings)
        monkeypatch.setattr(module, "create_engine", self.create_engine)
        monkeypatch.setattr(
            module, "create_session_factory", self.create_session_factory
        )
        monkeypatch.setattr(module, "QdrantStore", self.create_qdrant_store)
        monkeypatch.setattr(module, "EmbeddingClient", self.create_embedding_client)
        monkeypatch.setattr(module, "LLMClient", self.create_llm_client)
        monkeypatch.setattr(module, "RerankClient", self.create_rerank_client)
        monkeypatch.setattr(module.Redis, "from_url", staticmethod(self.create_redis))

    def patch_main(self, monkeypatch: MonkeyPatch, module: Any) -> None:
        self._patch_runtime_dependencies(monkeypatch, module)
        monkeypatch.setattr(module, "upgrade_database", self.upgrade_database)
        monkeypatch.setattr(
            module.ArqRedis, "from_url", staticmethod(self.create_job_queue)
        )

    def patch_worker(self, monkeypatch: MonkeyPatch, module: Any) -> None:
        self._patch_runtime_dependencies(monkeypatch, module)
        monkeypatch.setattr(module, "AragRouter", self.create_arag_router)
        monkeypatch.setattr(module, "configure_telemetry", self.configure_telemetry)
