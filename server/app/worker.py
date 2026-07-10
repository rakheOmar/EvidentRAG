from __future__ import annotations

import logging
from time import perf_counter

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
        embedding_client = EmbeddingClient(settings.embeddings)
        llm_client = LLMClient(settings.llm)
        rerank_client = RerankClient(settings.reranker)
        redis = Redis.from_url(settings.redis.url)
        arag_router = AragRouter(llm_client=llm_client)

        await qdrant_store.ensure_collection()

        ctx["engine"] = engine
        ctx["session_factory"] = session_factory
        ctx["qdrant_store"] = qdrant_store
        ctx["embedding_client"] = embedding_client
        ctx["llm_client"] = llm_client
        ctx["rerank_client"] = rerank_client
        ctx["redis"] = redis
        ctx["arag_router"] = arag_router

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


class WorkerSettings:
    functions = [run_message_pipeline]
    on_startup = staticmethod(startup)
    on_shutdown = staticmethod(shutdown)
    redis_settings = RedisSettings.from_dsn(settings.redis.url)
