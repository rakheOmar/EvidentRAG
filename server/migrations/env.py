from __future__ import annotations

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import create_engine

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return str(create_engine(get_settings().db).url).replace("+asyncpg", "")


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(), target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    options = config.get_section(config.config_ini_section) or {}
    options["sqlalchemy.url"] = _database_url()
    engine = engine_from_config(options, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
