from __future__ import annotations

import uuid
from unittest import mock

import pytest


pytestmark = pytest.mark.e2e


def test_health_sets_request_id_header(service_client) -> None:
    response = service_client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    uuid.UUID(response.headers["x-request-id"])


def test_health_returns_service_info(service_client) -> None:
    response = service_client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    svc = body["services"]

    assert svc["postgres"]["status"] == "healthy"
    assert svc["qdrant"]["status"] == "healthy"
    assert svc["redis"]["status"] == "healthy"
    assert all(set(details) == {"status"} for details in svc.values())


def test_health_degraded_when_redis_down(service_client) -> None:
    service_client.app.state.redis = mock.AsyncMock()
    service_client.app.state.redis.ping.side_effect = ConnectionError(
        "redis refused connection"
    )

    response = service_client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "degraded"
    assert body["services"]["redis"]["status"] == "unhealthy"
    assert set(body["services"]["redis"]) == {"status"}

    assert body["services"]["postgres"]["status"] == "healthy"
    assert body["services"]["qdrant"]["status"] == "healthy"


def test_health_degraded_when_qdrant_down(service_client) -> None:
    service_client.app.state.qdrant_store = mock.AsyncMock()
    service_client.app.state.qdrant_store.health_check.side_effect = ConnectionError(
        "qdrant refused connection"
    )

    response = service_client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "degraded"
    assert body["services"]["qdrant"]["status"] == "unhealthy"
    assert set(body["services"]["qdrant"]) == {"status"}

    assert body["services"]["postgres"]["status"] == "healthy"
    assert body["services"]["redis"]["status"] == "healthy"


class _FailingConn:
    async def __aenter__(self):
        raise ConnectionError("pg refused connection")

    async def __aexit__(self, *exc):
        pass


class _FailingEngine:
    connect = _FailingConn


def test_health_degraded_when_postgres_down(service_client) -> None:
    service_client.app.state.engine = _FailingEngine()

    response = service_client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "degraded"
    assert body["services"]["postgres"]["status"] == "unhealthy"
    assert set(body["services"]["postgres"]) == {"status"}

    assert body["services"]["qdrant"]["status"] == "healthy"
    assert body["services"]["redis"]["status"] == "healthy"
