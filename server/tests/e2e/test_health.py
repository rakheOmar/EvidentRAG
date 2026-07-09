from __future__ import annotations

import uuid
from unittest import mock


def test_health_sets_request_id_header(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["x-request-id"]
    uuid.UUID(response.headers["x-request-id"])


def test_health_returns_service_info(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ok"
    svc = body["services"]

    assert svc["postgres"]["status"] == "healthy"
    assert svc["postgres"]["host"] == "localhost:5432"
    tables = {t["name"]: t["rows"] for t in svc["postgres"]["tables"]}
    assert tables["documents"] >= 0
    assert tables["evidence"] >= 0

    assert svc["qdrant"]["status"] == "healthy"
    assert svc["qdrant"]["url"] == "http://localhost:6333"
    collections = {c["name"]: c["points"] for c in svc["qdrant"]["collections"]}
    assert collections["evidentrag_evidence"] >= 0

    assert svc["redis"]["status"] == "healthy"
    assert svc["redis"]["url"] in ("redis://localhost:6379", "redis://localhost:6379/0")


def test_health_degraded_when_redis_down(client) -> None:
    client.app.state.redis = mock.AsyncMock()
    client.app.state.redis.ping.side_effect = ConnectionError(
        "redis refused connection"
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "degraded"
    assert body["services"]["redis"]["status"] == "unhealthy"
    assert "redis refused connection" in body["services"]["redis"]["error"]

    assert body["services"]["postgres"]["status"] == "healthy"
    assert body["services"]["qdrant"]["status"] == "healthy"


def test_health_degraded_when_qdrant_down(client) -> None:
    client.app.state.qdrant_store = mock.AsyncMock()
    client.app.state.qdrant_store._client = mock.AsyncMock()
    client.app.state.qdrant_store._client.get_collections.side_effect = ConnectionError(
        "qdrant refused connection"
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "degraded"
    assert body["services"]["qdrant"]["status"] == "unhealthy"
    assert "qdrant refused connection" in body["services"]["qdrant"]["error"]

    assert body["services"]["postgres"]["status"] == "healthy"
    assert body["services"]["redis"]["status"] == "healthy"


class _FailingConn:
    async def __aenter__(self):
        raise ConnectionError("pg refused connection")

    async def __aexit__(self, *exc):
        pass


class _FailingEngine:
    connect = _FailingConn


def test_health_degraded_when_postgres_down(client) -> None:
    client.app.state.engine = _FailingEngine()

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "degraded"
    assert body["services"]["postgres"]["status"] == "unhealthy"
    assert "pg refused connection" in body["services"]["postgres"]["error"]

    assert body["services"]["qdrant"]["status"] == "healthy"
    assert body["services"]["redis"]["status"] == "healthy"
