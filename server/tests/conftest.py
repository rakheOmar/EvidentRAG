from __future__ import annotations

from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.main import app
from sqlalchemy import text

from app.infrastructure.db.models import Base


@pytest.fixture
def client() -> Iterator[TestClient]:
    try:
        with TestClient(app) as test_client:

            async def _reset_schema() -> None:
                test_app = cast("object", test_client.app)
                state = getattr(test_app, "state")
                async with state.engine.begin() as conn:
                    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
                    await conn.execute(text("CREATE SCHEMA public"))
                    await conn.run_sync(Base.metadata.create_all)

            assert test_client.portal is not None
            test_client.portal.call(_reset_schema)
            yield test_client
    except (ConnectionRefusedError, RedisError) as exc:
        pytest.skip(f"integration stack unavailable: {exc}")
