from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.api.middleware.access_logging import RequestObservabilityMiddleware


def test_request_emits_one_enriched_completion_event(caplog) -> None:
    app = FastAPI()
    app.add_middleware(RequestObservabilityMiddleware)

    @app.get("/documents/{document_id}")
    async def get_document(document_id: str, request: Request) -> dict[str, str]:
        request.state.wide_event["document"] = {"id": document_id}
        return {"document_id": document_id}

    caplog.set_level(logging.INFO, logger="app.access")
    document_id = str(uuid.uuid4())

    with TestClient(app) as client:
        response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    request_id = response.headers["x-request-id"]
    uuid.UUID(request_id)

    records = [record for record in caplog.records if record.name == "app.access"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    wide_event = records[0].wide_event
    assert wide_event == {
        "event": "request_completed",
        "request_id": request_id,
        "http_request_method": "GET",
        "url_path": f"/documents/{document_id}",
        "url_scheme": "http",
        "network_protocol_version": "1.1",
        "client_address": "testclient",
        "user_agent_original": "testclient",
        "http_route": "/documents/{document_id}",
        "http_response_status_code": 200,
        "http_response_body_size": len(response.content),
        "outcome": "success",
        "document": {"id": document_id},
        "duration_ms": wide_event["duration_ms"],
    }


def test_server_error_emits_error_completion_event(caplog) -> None:
    app = FastAPI()
    app.add_middleware(RequestObservabilityMiddleware)

    @app.get("/failure")
    async def fail() -> JSONResponse:
        return JSONResponse({"error": "unavailable"}, status_code=503)

    caplog.set_level(logging.INFO, logger="app.access")

    with TestClient(app) as client:
        response = client.get("/failure", headers={"x-request-id": "request-123"})

    assert response.status_code == 503
    assert response.headers["x-request-id"] == "request-123"

    records = [record for record in caplog.records if record.name == "app.access"]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].wide_event["request_id"] == "request-123"
    assert records[0].wide_event["http_response_status_code"] == 503
    assert records[0].wide_event["outcome"] == "error"
