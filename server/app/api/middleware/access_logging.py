from __future__ import annotations

import logging
from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_request_id

logger = logging.getLogger("app.access")


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started_at = perf_counter()

        request_id = (
            getattr(request.state, "request_id", None)
            or get_request_id()
            or request.headers.get("x-request-id")
        )

        wide_event: dict[str, object] = {
            "event": "request_completed",
            "http_method": request.method,
            "http_path": request.url.path,
            "request_id": request_id,
        }
        request.state.wide_event = wide_event

        try:
            response = await call_next(request)
            wide_event["http_status_code"] = response.status_code
            wide_event["outcome"] = "success" if response.status_code < 400 else "error"
            return response
        except Exception as exc:
            wide_event["http_status_code"] = 500
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            raise
        finally:
            wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            logger.info("request_completed", extra={"wide_event": wide_event})
