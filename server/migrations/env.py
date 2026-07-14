from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import URL, pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import build_database_url

config = context.config
target_metadata = Base.metadata


def _database_url() -> URL:
    configured = config.attributes.get("database_url")
    if isinstance(configured, URL):
        return configured
    return build_database_url(get_settings().db)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url().render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online() -> None:
    options = config.get_section(config.config_ini_section) or {}
    options["sqlalchemy.url"] = _database_url().render_as_string(hide_password=False)
    engine = async_engine_from_config(
        options, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with engine.connect() as connection:
        await connection.run_sync(_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
