from __future__ import annotations

import logging
from time import perf_counter
import uuid

from opentelemetry import trace
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import (
    reset_request_id,
    reset_wide_event,
    set_request_id,
    set_wide_event,
)

logger = logging.getLogger("app.access")


class RequestObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        started_at = perf_counter()
        request_id = _request_id(scope)
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        wide_event: dict[str, object] = {
            "event": "request_completed",
            "request_id": request_id,
            "http_request_method": scope["method"],
            "url_path": scope["path"],
            "url_scheme": scope["scheme"],
            "network_protocol_version": scope["http_version"],
        }
        headers = Headers(scope=scope)
        client = scope.get("client")
        if client:
            wide_event["client_address"] = client[0]
        if user_agent := headers.get("user-agent"):
            wide_event["user_agent_original"] = user_agent
        if content_length := headers.get("content-length"):
            try:
                wide_event["http_request_body_size"] = int(content_length)
            except ValueError:
                pass
        state["wide_event"] = wide_event
        status_code = 500
        response_body_size = 0
        context_token = set_request_id(request_id)
        wide_event_token = set_wide_event(wide_event)

        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("app.request.id", request_id)

        async def send_with_context(message: Message) -> None:
            nonlocal response_body_size, status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)["x-request-id"] = request_id
            elif message["type"] == "http.response.body":
                response_body_size += len(message.get("body", b""))
            await send(message)

        try:
            await self._app(scope, receive, send_with_context)
            wide_event["outcome"] = "success" if status_code < 400 else "error"
        except Exception as exc:
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            raise
        finally:
            route = scope.get("route")
            route_path = getattr(route, "path", None)
            if route_path:
                wide_event["http_route"] = route_path
            wide_event["http_response_status_code"] = status_code
            wide_event["http_response_body_size"] = response_body_size
            wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            log = logger.error if status_code >= 500 else logger.info
            log("request_completed", extra={"wide_event": wide_event})
            reset_wide_event(wide_event_token)
            reset_request_id(context_token)


def _request_id(scope: Scope) -> str:
    request_id = (Headers(scope=scope).get("x-request-id") or "").strip()
    if request_id and len(request_id) <= 128:
        return request_id
    return str(uuid.uuid4())
