from __future__ import annotations

from arq.connections import RedisSettings
from redis.asyncio import Redis

from app.application.query_pipeline.query_pipeline import QueryPipeline
from app.core.config import get_settings
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.embeddings.embedding import EmbeddingClient
from app.infrastructure.llm.llm import LLMClient
from app.infrastructure.qdrant.client import QdrantStore
from app.infrastructure.reranker.reranker import RerankClient

settings = get_settings()


async def startup(ctx: dict) -> None:
    engine = create_engine(settings.db)
    session_factory = create_session_factory(engine)
    qdrant_store = QdrantStore(settings.qdrant)
    embedding_client = EmbeddingClient(settings.embeddings)
    llm_client = LLMClient(settings.llm)
    rerank_client = RerankClient(settings.cohere)
    redis = Redis.from_url(settings.redis.url)

    await qdrant_store.ensure_collection()

    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["qdrant_store"] = qdrant_store
    ctx["embedding_client"] = embedding_client
    ctx["llm_client"] = llm_client
    ctx["rerank_client"] = rerank_client
    ctx["redis"] = redis


async def shutdown(ctx: dict) -> None:
    redis = ctx.get("redis")
    if redis is not None:
        await redis.aclose()

    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


async def run_query_pipeline(ctx: dict, query_id) -> None:
    pipeline = QueryPipeline(
        session_factory=ctx["session_factory"],
        redis=ctx["redis"],
        embedding_client=ctx["embedding_client"],
        qdrant_store=ctx["qdrant_store"],
        rerank_client=ctx["rerank_client"],
        llm_client=ctx["llm_client"],
    )
    await pipeline.run(query_id)


class WorkerSettings:
    functions = [run_query_pipeline]
    on_startup = staticmethod(startup)
    on_shutdown = staticmethod(shutdown)
    redis_settings = RedisSettings.from_dsn(settings.redis.url)
