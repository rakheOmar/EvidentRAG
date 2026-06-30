from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis

from app.api.middleware.access_logging import AccessLoggingMiddleware
from app.api.middleware.request_context import RequestContextMiddleware
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.telemetry import configure_telemetry
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.embeddings.embedding import EmbeddingClient
from app.infrastructure.qdrant.client import QdrantStore
from app.seed.seed_demo_data import seed_demo_data


settings = get_settings()
configure_logging(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_telemetry(app, settings)
    engine = create_engine(settings.db)
    session_factory = create_session_factory(engine)
    qdrant_store = QdrantStore(settings.qdrant)
    redis = Redis.from_url(settings.redis.url)

    app.state.settings = settings
    app.state.engine = engine
    app.state.qdrant_store = qdrant_store
    app.state.redis = redis

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await qdrant_store.ensure_collection()

    if settings.embeddings.seed_demo_data:
        embedding_client = EmbeddingClient(settings.embeddings)
        await seed_demo_data(
            session_factory=session_factory,
            qdrant_store=qdrant_store,
            embedding_client=embedding_client,
        )
    yield

    await redis.aclose()
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(AccessLoggingMiddleware)
app.include_router(health_router)
