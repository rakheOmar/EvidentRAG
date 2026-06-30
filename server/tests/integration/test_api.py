from __future__ import annotations

import logging


def test_health_preserves_incoming_request_id(client) -> None:
    response = client.get("/health", headers={"x-request-id": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-id"


def test_access_log_includes_request_metadata(client, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.access")

    response = client.get("/health", headers={"x-request-id": "log-test-id"})

    assert response.status_code == 200

    records = [record for record in caplog.records if record.name == "app.access"]
    assert len(records) == 1

    record = records[0]
    assert record.msg == "request_completed"
    assert record.http_method == "GET"
    assert record.http_path == "/health"
    assert record.http_status_code == 200
    assert record.request_id == "log-test-id"
    assert isinstance(record.duration_ms, float)
