from __future__ import annotations

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings


def build_database_url(settings: DatabaseSettings) -> URL:
    return URL.create(
        drivername="postgresql+asyncpg",
        username=settings.user,
        password=settings.password or "",
        host=settings.host,
        port=settings.port,
        database=settings.db,
    )


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(build_database_url(settings))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)
