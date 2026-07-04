from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    try:
        with TestClient(app) as test_client:
            yield test_client
    except (ConnectionRefusedError, RedisError) as exc:
        pytest.skip(f"integration stack unavailable: {exc}")
