from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import DatabaseSettings
from app.infrastructure.db.session import build_database_url, create_engine


def _adoption_revision(table_names: set[str], document_columns: set[str]) -> str | None:
    if "alembic_version" in table_names or "documents" not in table_names:
        return None
    current_columns = {"source_id", "version_number", "status", "is_current"}
    if "sources" in table_names and current_columns.issubset(document_columns):
        return "20260711_01"
    return "20260630_00"


async def _detect_adoption_revision(settings: DatabaseSettings) -> str | None:
    engine = create_engine(settings)
    try:
        async with engine.connect() as connection:

            def inspect_schema(sync_connection) -> str | None:
                inspector = inspect(sync_connection)
                table_names = set(inspector.get_table_names())
                document_columns = (
                    {column["name"] for column in inspector.get_columns("documents")}
                    if "documents" in table_names
                    else set()
                )
                return _adoption_revision(table_names, document_columns)

            return await connection.run_sync(inspect_schema)
    finally:
        await engine.dispose()


def upgrade_database(settings: DatabaseSettings) -> None:
    server_root = Path(__file__).resolve().parents[3]
    config = Config(str(server_root / "alembic.ini"))
    config.attributes["database_url"] = build_database_url(settings)
    adoption_revision = asyncio.run(_detect_adoption_revision(settings))
    if adoption_revision is not None:
        command.stamp(config, adoption_revision)
    command.upgrade(config, "head")
