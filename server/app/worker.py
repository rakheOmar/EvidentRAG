from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import logging
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Mapping

from arq import func
from arq.cron import cron
from arq.connections import RedisSettings
from opentelemetry import context as otel_context, propagate, trace
from opentelemetry.trace import SpanKind
from redis.asyncio import Redis

from app.application.query_pipeline.arag_router import AragRouter
from app.application.query_pipeline.query_pipeline import (
    NonRetryablePipelineError,
    QueryPipeline,
)
from app.core.config import get_settings
from app.core.logging import (
    configure_logging,
    reset_request_id,
    reset_wide_event,
    set_request_id,
    set_wide_event,
)
from app.core.telemetry import configure_telemetry
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.embeddings.embedding import EmbeddingClient
from app.infrastructure.llm.llm import LLMClient
from app.infrastructure.qdrant.client import QdrantStore
from app.infrastructure.reranker.reranker import RerankClient
from app.infrastructure.ai.scheduler import AIRequestScheduler
from app.application.ingestion.pipeline import DocumentIngestionPipeline
from app.infrastructure.storage.local import LocalDocumentStorage
from app.infrastructure.db.models import Document, Source
from sqlalchemy import select

settings = get_settings()
configure_logging(settings)

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    started_at = perf_counter()
    wide_event: dict[str, object] = {
        "event": "worker_startup",
        "configuration": {
            "otel_enabled": settings.otel.enabled,
            "otel_protocol": settings.otel.exporter_otlp_protocol,
            "generation_model": settings.llm.generation_model,
            "utility_model": settings.llm.utility_model,
            "embedding_model": settings.embeddings.model,
            "reranker_model": settings.reranker.model,
        },
    }
    telemetry = None
    wide_event_token = set_wide_event(wide_event)

    try:
        telemetry = configure_telemetry(None, settings)
        ctx["telemetry"] = telemetry
        engine = create_engine(settings.db)
        if telemetry is not None:
            telemetry.instrument_sqlalchemy(engine)
        session_factory = create_session_factory(engine)
        qdrant_store = QdrantStore(settings.qdrant)
        redis = Redis.from_url(settings.redis.url)
        scheduler = AIRequestScheduler(redis, settings.rate_limits)
        embedding_client = EmbeddingClient(settings.embeddings, scheduler=scheduler)
        llm_client = LLMClient(settings.llm, scheduler=scheduler)
        rerank_client = RerankClient(settings.reranker, scheduler=scheduler)
        arag_router = AragRouter(llm_client=llm_client)

        try:
            llm_client.set_model_catalog(await llm_client.list_models())
        except Exception as exc:
            wide_event["model_catalog"] = {
                "outcome": "degraded",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            }

        await qdrant_store.ensure_collection()

        ctx["engine"] = engine
        ctx["session_factory"] = session_factory
        ctx["qdrant_store"] = qdrant_store
        ctx["embedding_client"] = embedding_client
        ctx["llm_client"] = llm_client
        ctx["rerank_client"] = rerank_client
        ctx["redis"] = redis
        ctx["arag_router"] = arag_router
        ctx["document_storage"] = LocalDocumentStorage(settings.ingestion.storage_path)

        wide_event["outcome"] = "success"
    except Exception as exc:
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        if telemetry is not None:
            telemetry.shutdown()
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        log = logger.error if wide_event.get("outcome") == "error" else logger.info
        try:
            log("worker_startup", extra={"wide_event": wide_event})
        finally:
            reset_wide_event(wide_event_token)


async def shutdown(ctx: dict) -> None:
    started_at = perf_counter()
    wide_event: dict[str, object] = {"event": "worker_shutdown"}

    try:
        redis = ctx.get("redis")
        if redis is not None:
            await redis.aclose()

        engine = ctx.get("engine")
        if engine is not None:
            await engine.dispose()

        telemetry = ctx.get("telemetry")
        if telemetry is not None:
            telemetry.shutdown()

        wide_event["outcome"] = "success"
    except Exception as exc:
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        log = logger.error if wide_event.get("outcome") == "error" else logger.info
        log("worker_shutdown", extra={"wide_event": wide_event})


async def run_message_pipeline(
    ctx: dict,
    message_id,
    trace_context: Mapping[str, str] | None = None,
) -> None:
    with _job_observability(
        "run_message_pipeline",
        {"message_id": str(message_id)},
        trace_context,
    ) as wide_event:
        try:
            pipeline = QueryPipeline(
                session_factory=ctx["session_factory"],
                redis=ctx["redis"],
                embedding_client=ctx["embedding_client"],
                qdrant_store=ctx["qdrant_store"],
                rerank_client=ctx["rerank_client"],
                llm_client=ctx["llm_client"],
                arag_router=ctx.get("arag_router"),
            )
            await pipeline.run(message_id)
            wide_event["outcome"] = "success"
        except NonRetryablePipelineError as exc:
            wide_event["outcome"] = "skipped"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)


async def run_document_ingestion(
    ctx: dict,
    document_id,
    trace_context: Mapping[str, str] | None = None,
) -> None:
    document_id = str(document_id)
    with _job_observability(
        "run_document_ingestion",
        {"document_id": document_id},
        trace_context,
    ) as wide_event:
        pipeline = DocumentIngestionPipeline(
            session_factory=ctx["session_factory"],
            redis=ctx["redis"],
            embedding_client=ctx["embedding_client"],
            llm_client=ctx["llm_client"],
            qdrant_store=ctx["qdrant_store"],
            storage=ctx["document_storage"],
        )
        await pipeline.run(document_id)
        wide_event["outcome"] = "success"


@contextmanager
def _job_observability(
    job_name: str,
    identity: dict[str, object],
    trace_context: Mapping[str, str] | None,
) -> Iterator[dict[str, object]]:
    started_at = perf_counter()
    wide_event: dict[str, object] = {"event": job_name, **identity}
    request_id = (trace_context or {}).get("x-request-id")
    if request_id:
        wide_event["request_id"] = request_id

    request_token = set_request_id(request_id)
    wide_event_token = set_wide_event(wide_event)
    parent_context = propagate.extract(trace_context or {})
    context_token = otel_context.attach(parent_context)

    try:
        tracer = trace.get_tracer(__name__)
        span_attributes: dict[str, bool | int | float | str] = {
            "messaging.system": "redis",
            "messaging.operation.name": job_name,
            "messaging.operation.type": "process",
        }
        message_id = identity.get("message_id") or identity.get("document_id")
        if message_id is not None:
            span_attributes["messaging.message.id"] = str(message_id)
        with tracer.start_as_current_span(
            job_name,
            kind=SpanKind.CONSUMER,
            attributes=span_attributes,
        ):
            try:
                yield wide_event
            except Exception as exc:
                wide_event["outcome"] = "error"
                wide_event["error_type"] = type(exc).__name__
                wide_event["error_message"] = str(exc)
                raise
            finally:
                wide_event["duration_ms"] = round(
                    (perf_counter() - started_at) * 1000, 2
                )
                log = (
                    logger.error
                    if wide_event.get("outcome") == "error"
                    else logger.info
                )
                log(job_name, extra={"wide_event": wide_event})
    finally:
        otel_context.detach(context_token)
        reset_wide_event(wide_event_token)
        reset_request_id(request_token)


async def cleanup_deleted_documents(ctx: dict) -> None:
    with _job_observability(
        "deleted_document_cleanup",
        {"retention_days": settings.ingestion.audit_retention_days},
        None,
    ) as wide_event:
        deleted_sources = 0
        deleted_documents = 0
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.ingestion.audit_retention_days
        )
        storage = ctx["document_storage"]
        async with ctx["session_factory"]() as session:
            sources = await session.scalars(
                select(Source).where(
                    Source.deleted_at.is_not(None), Source.deleted_at <= cutoff
                )
            )
            for source in sources:
                deleted_sources += 1
                documents = list(
                    await session.scalars(
                        select(Document).where(Document.source_id == source.id)
                    )
                )
                for document in documents:
                    deleted_documents += 1
                    await ctx["qdrant_store"].delete_document_points(str(document.id))
                    if document.storage_key:
                        storage.delete(document.storage_key)
                    await session.delete(document)
                await session.delete(source)
            await session.commit()
        wide_event["deleted_sources"] = deleted_sources
        wide_event["deleted_documents"] = deleted_documents
        wide_event["outcome"] = "success"


class WorkerSettings:
    functions = [
        run_message_pipeline,
        func(
            run_document_ingestion,
            max_tries=settings.ingestion.retry_attempts,
            timeout=settings.ingestion.job_timeout_seconds,
        ),
    ]
    cron_jobs = [cron(cleanup_deleted_documents, hour=3, minute=0, unique=True)]
    on_startup = staticmethod(startup)
    on_shutdown = staticmethod(shutdown)
    redis_settings = RedisSettings.from_dsn(settings.redis.url)
