from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        415: "unsupported_media_type",
        413: "payload_too_large",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_server_error",
        503: "service_unavailable",
    }.get(status_code, "request_failed")


def _message(detail: object, fallback: str) -> tuple[str, dict[str, object]]:
    if isinstance(detail, Mapping):
        return str(detail.get("message", fallback)), dict(detail)
    return str(detail) if detail else fallback, {}


def _body(request: Request, status_code: int, detail: object, fallback: str) -> dict:
    message, details = _message(detail, fallback)
    return {
        "error": {
            "code": _code(status_code),
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    http_exc = cast(HTTPException, exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=_body(request, http_exc.status_code, http_exc.detail, "Request failed"),
        headers=http_exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    validation_exc = cast(RequestValidationError, exc)
    return JSONResponse(
        status_code=422,
        content=_body(
            request,
            422,
            {"message": "Request validation failed", "fields": validation_exc.errors()},
            "Request validation failed",
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=_body(request, 500, "Internal server error", "Internal server error"),
    )
