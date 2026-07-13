from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
import os
from typing import cast

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError
from sqlalchemy import text

from app import main as main_module
from app.core.config import DatabaseSettings, Settings
from app.infrastructure.db.models import Base


def _is_disposable_database(database_name: str) -> bool:
    normalized = database_name.casefold()
    return normalized.startswith("test_") or normalized.endswith("_test")


def _destructive_schema_reset_enabled() -> bool:
    return os.getenv("TEST_ALLOW_DESTRUCTIVE_SCHEMA_RESET", "").casefold() == "true"


def _integration_settings(settings: Settings) -> Settings:
    database_name = os.getenv("TEST_POSTGRES_DB")
    if database_name is None:
        pytest.skip(
            "integration tests require TEST_POSTGRES_DB to name a disposable database"
        )

    if not _is_disposable_database(database_name):
        pytest.fail(
            "refusing destructive integration setup: TEST_POSTGRES_DB must "
            "start with 'test_' or end with '_test'"
        )
    if not _destructive_schema_reset_enabled():
        pytest.skip(
            "integration tests require TEST_ALLOW_DESTRUCTIVE_SCHEMA_RESET=true"
        )

    database = DatabaseSettings(
        host=os.getenv("TEST_POSTGRES_HOST", settings.db.host),
        port=int(os.getenv("TEST_POSTGRES_PORT", str(settings.db.port))),
        user=os.getenv("TEST_POSTGRES_USER", settings.db.user),
        password=os.getenv("TEST_POSTGRES_PASSWORD", settings.db.password),
        db=database_name,
    )
    return replace(settings, db=database)


def _test_client(*, reset_schema: bool) -> Iterator[TestClient]:
    original_settings = main_module.settings
    main_module.settings = _integration_settings(original_settings)
    try:
        with TestClient(main_module.app) as test_client:

            async def _reset_schema() -> None:
                test_app = cast("object", test_client.app)
                state = getattr(test_app, "state")
                async with state.engine.begin() as conn:
                    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                    await conn.execute(text("CREATE SCHEMA public"))
                    await conn.run_sync(Base.metadata.create_all)

            if reset_schema:
                assert test_client.portal is not None
                test_client.portal.call(_reset_schema)
            yield test_client
    except (ConnectionRefusedError, RedisError) as exc:
        pytest.skip(f"integration stack unavailable: {exc}")
    finally:
        main_module.settings = original_settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield from _test_client(reset_schema=True)


@pytest.fixture
def service_client() -> Iterator[TestClient]:
    yield from _test_client(reset_schema=False)
