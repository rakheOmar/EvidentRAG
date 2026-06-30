from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings


def _build_url(settings: DatabaseSettings) -> str:
    password = settings.password or ""
    return (
        f"postgresql+asyncpg://{settings.user}:{password}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(_build_url(settings))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
