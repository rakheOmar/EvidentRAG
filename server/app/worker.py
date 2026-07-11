from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from time import perf_counter

from arq import func
from arq.cron import cron
from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.application.query_pipeline.arag_router import AragRouter
from app.application.query_pipeline.query_pipeline import (
    NonRetryablePipelineError,
    QueryPipeline,
)
from app.core.config import get_settings
from app.core.logging import configure_logging
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
    wide_event: dict[str, object] = {"event": "worker_startup"}

    try:
        engine = create_engine(settings.db)
        session_factory = create_session_factory(engine)
        qdrant_store = QdrantStore(settings.qdrant)
        redis = Redis.from_url(settings.redis.url)
        scheduler = AIRequestScheduler(redis, settings.rate_limits)
        embedding_client = EmbeddingClient(settings.embeddings)
        llm_client = LLMClient(settings.llm, scheduler=scheduler)
        rerank_client = RerankClient(settings.reranker, scheduler=scheduler)
        arag_router = AragRouter(llm_client=llm_client)

        try:
            llm_client.set_model_catalog(await llm_client.list_models())
        except Exception as exc:
            logger.warning(
                "worker_model_catalog_load_failed",
                extra={
                    "wide_event": {
                        "event": "worker_model_catalog_load_failed",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                        "outcome": "degraded",
                    }
                },
            )

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
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        logger.info("worker_startup", extra={"wide_event": wide_event})


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

        wide_event["outcome"] = "success"
    except Exception as exc:
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        logger.info("worker_shutdown", extra={"wide_event": wide_event})


async def run_message_pipeline(ctx: dict, message_id) -> None:
    started_at = perf_counter()
    wide_event: dict[str, object] = {
        "event": "run_message_pipeline",
        "message_id": str(message_id),
    }

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
        logger.warning("run_message_pipeline skipped", extra={"wide_event": wide_event})
    except Exception as exc:
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        logger.info("run_message_pipeline", extra={"wide_event": wide_event})


async def run_document_ingestion(ctx: dict, document_id) -> None:
    pipeline = DocumentIngestionPipeline(
        session_factory=ctx["session_factory"],
        redis=ctx["redis"],
        embedding_client=ctx["embedding_client"],
        llm_client=ctx["llm_client"],
        qdrant_store=ctx["qdrant_store"],
        storage=ctx["document_storage"],
    )
    await pipeline.run(str(document_id))


async def cleanup_deleted_documents(ctx: dict) -> None:
    started_at = perf_counter()
    wide_event: dict[str, object] = {
        "event": "deleted_document_cleanup",
        "retention_days": settings.ingestion.audit_retention_days,
        "deleted_sources": 0,
        "deleted_documents": 0,
    }
    deleted_sources = 0
    deleted_documents = 0
    try:
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
    except Exception as exc:
        wide_event["outcome"] = "error"
        wide_event["error_type"] = type(exc).__name__
        wide_event["error_message"] = str(exc)
        raise
    finally:
        wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
        logger.info("deleted_document_cleanup", extra={"wide_event": wide_event})


class WorkerSettings:
    functions = [
        run_message_pipeline,
        func(run_document_ingestion, max_tries=settings.ingestion.retry_attempts),
    ]
    cron_jobs = [cron(cleanup_deleted_documents, hour=3, minute=0, unique=True)]
    on_startup = staticmethod(startup)
    on_shutdown = staticmethod(shutdown)
    redis_settings = RedisSettings.from_dsn(settings.redis.url)
