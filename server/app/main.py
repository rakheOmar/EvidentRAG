import logging
from contextlib import asynccontextmanager
from time import perf_counter

from arq.connections import ArqRedis
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from redis.asyncio import Redis

from app.api.middleware.access_logging import RequestObservabilityMiddleware
from app.api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.api.routes.health import router as health_router
from app.api.routes.documents import router as documents_router
from app.api.routes.models import router as models_router
from app.api.routes.sentence_traces import router as sentence_traces_router
from app.api.routes.threads import router as threads_router
from app.frontend import mount_frontend

from app.core.config import get_settings
from app.core.logging import (
    configure_logging,
    reset_wide_event,
    set_wide_event,
)
from app.core.telemetry import configure_telemetry
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.embeddings.embedding import EmbeddingClient
from app.infrastructure.llm.llm import LLMClient
from app.infrastructure.qdrant.client import QdrantStore
from app.infrastructure.reranker.reranker import RerankClient
from app.infrastructure.storage.local import LocalDocumentStorage
from app.infrastructure.ai.scheduler import AIRequestScheduler
from app.seed.seed_demo_data import seed_demo_data


settings = get_settings()
configure_logging(settings)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_started_at = perf_counter()
    startup_event: dict[str, object] = {
        "event": "app_startup",
        "seed_demo_data_enabled": settings.embeddings.seed_demo_data,
        "configuration": {
            "otel_enabled": settings.otel.enabled,
            "otel_protocol": settings.otel.exporter_otlp_protocol,
            "generation_model": settings.llm.generation_model,
            "utility_model": settings.llm.utility_model,
            "embedding_model": settings.embeddings.model,
            "reranker_model": settings.reranker.model,
            "evidence_collection": settings.qdrant.evidence_collection,
        },
    }
    engine = None
    redis = None
    job_queue = None
    wide_event_token = set_wide_event(startup_event)
    startup_context_active = True
    startup_logged = False

    try:
        startup_event["telemetry_configured"] = app.state.telemetry is not None

        engine = create_engine(settings.db)
        if app.state.telemetry is not None:
            app.state.telemetry.instrument_sqlalchemy(engine)
        session_factory = create_session_factory(engine)
        qdrant_store = QdrantStore(settings.qdrant)
        redis = Redis.from_url(settings.redis.url)
        scheduler = AIRequestScheduler(redis, settings.rate_limits)
        embedding_client = EmbeddingClient(settings.embeddings)
        llm_client = LLMClient(settings.llm, scheduler=scheduler)
        rerank_client = RerankClient(settings.reranker, scheduler=scheduler)
        job_queue = ArqRedis.from_url(settings.redis.url)

        try:
            model_catalog = await llm_client.list_models()
        except Exception as exc:
            model_catalog = []
            startup_event["model_catalog"] = {
                "outcome": "degraded",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }
        set_model_catalog = getattr(llm_client, "set_model_catalog", None)
        if callable(set_model_catalog):
            set_model_catalog(model_catalog)

        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.qdrant_store = qdrant_store
        app.state.embedding_client = embedding_client
        app.state.llm_client = llm_client
        app.state.context_manager = getattr(llm_client, "context_manager", None)
        app.state.model_catalog = model_catalog
        app.state.rerank_client = rerank_client
        app.state.redis = redis
        app.state.job_queue = job_queue
        app.state.document_storage = LocalDocumentStorage(
            settings.ingestion.storage_path
        )
        startup_event["runtime_dependencies_initialized"] = True

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        startup_event["database_schema_ready"] = True

        await qdrant_store.ensure_collection()
        startup_event["qdrant_collection_ready"] = True

        if settings.embeddings.seed_demo_data:
            seeded_count = await seed_demo_data(
                session_factory=session_factory,
                qdrant_store=qdrant_store,
                embedding_client=embedding_client,
            )
            startup_event["seeded_documents"] = seeded_count

        startup_event["outcome"] = "success"
        startup_event["duration_ms"] = round(
            (perf_counter() - startup_started_at) * 1000, 2
        )
        logger.info("app_startup", extra={"wide_event": startup_event})
        startup_logged = True
        reset_wide_event(wide_event_token)
        startup_context_active = False

        yield
    except Exception as exc:
        if not startup_logged:
            startup_event["outcome"] = "error"
            startup_event["error_type"] = type(exc).__name__
            startup_event["error_message"] = str(exc)
            startup_event["duration_ms"] = round(
                (perf_counter() - startup_started_at) * 1000, 2
            )
            logger.error("app_startup", extra={"wide_event": startup_event})
        raise
    finally:
        if startup_context_active:
            reset_wide_event(wide_event_token)
        shutdown_started_at = perf_counter()
        shutdown_event: dict[str, object] = {"event": "app_shutdown"}
        try:
            if job_queue is not None:
                await job_queue.aclose()
                shutdown_event["job_queue_closed"] = True
            if redis is not None:
                await redis.aclose()
                shutdown_event["redis_closed"] = True
            if engine is not None:
                await engine.dispose()
                shutdown_event["engine_disposed"] = True
            telemetry = getattr(app.state, "telemetry", None)
            if telemetry is not None:
                telemetry.shutdown()
                shutdown_event["telemetry_shutdown"] = True
            shutdown_event["outcome"] = "success"
        except Exception as exc:
            shutdown_event["outcome"] = "error"
            shutdown_event["error_type"] = type(exc).__name__
            shutdown_event["error_message"] = str(exc)
            raise
        finally:
            shutdown_event["duration_ms"] = round(
                (perf_counter() - shutdown_started_at) * 1000, 2
            )
            log = (
                logger.error
                if shutdown_event.get("outcome") == "error"
                else logger.info
            )
            log("app_shutdown", extra={"wide_event": shutdown_event})


app = FastAPI(title=settings.app.app_name, lifespan=lifespan)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.add_middleware(RequestObservabilityMiddleware)
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(models_router)
app.include_router(sentence_traces_router)
app.include_router(threads_router)
mount_frontend(app, settings)
app.state.telemetry = configure_telemetry(app, settings)
