from contextlib import asynccontextmanager

from arq.connections import ArqRedis
from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.middleware.access_logging import AccessLoggingMiddleware
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.routes.health import router as health_router
from app.api.routes.queries import router as queries_router
from app.frontend import mount_frontend
from dotenv import load_dotenv

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.telemetry import configure_telemetry
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.embeddings.embedding import EmbeddingClient
from app.infrastructure.llm.llm import LLMClient
from app.infrastructure.qdrant.client import QdrantStore
from app.infrastructure.reranker.reranker import RerankClient
from app.seed.seed_demo_data import seed_demo_data


load_dotenv()
settings = get_settings()
configure_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_telemetry(app, settings)
    engine = create_engine(settings.db)
    session_factory = create_session_factory(engine)
    qdrant_store = QdrantStore(settings.qdrant)
    embedding_client = EmbeddingClient(settings.embeddings)
    llm_client = LLMClient(settings.llm)
    rerank_client = RerankClient(settings.reranker)
    redis = Redis.from_url(settings.redis.url)
    job_queue = ArqRedis.from_url(settings.redis.url)

    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.qdrant_store = qdrant_store
    app.state.embedding_client = embedding_client
    app.state.llm_client = llm_client
    app.state.rerank_client = rerank_client
    app.state.redis = redis
    app.state.job_queue = job_queue

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await qdrant_store.ensure_collection()

    if settings.embeddings.seed_demo_data:
        await seed_demo_data(
            session_factory=session_factory,
            qdrant_store=qdrant_store,
            embedding_client=embedding_client,
        )
    yield

    await job_queue.aclose()
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title=settings.app.app_name, lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(AccessLoggingMiddleware)
app.include_router(health_router)
app.include_router(queries_router)
mount_frontend(app, settings)
