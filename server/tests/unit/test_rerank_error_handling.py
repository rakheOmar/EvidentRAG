from __future__ import annotations

import httpx

from app.application.query_pipeline.query_pipeline import QueryPipeline


def _make_pipeline() -> QueryPipeline:
    return QueryPipeline(session_factory=lambda: None, redis=object())


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.cohere.com/v2/rerank")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def test_handle_rerank_error_degrades_on_timeout() -> None:
    pipeline = _make_pipeline()
    exc = httpx.TimeoutException("timed out")
    assert pipeline._handle_rerank_error(exc, 7) is True


def test_handle_rerank_error_degrades_on_retryable_status() -> None:
    pipeline = _make_pipeline()
    assert pipeline._handle_rerank_error(_status_error(503), 7) is True
    assert pipeline._handle_rerank_error(_status_error(429), 7) is True


def test_handle_rerank_error_reraises_on_non_retryable_status() -> None:
    pipeline = _make_pipeline()
    assert pipeline._handle_rerank_error(_status_error(400), 7) is False
    assert pipeline._handle_rerank_error(_status_error(401), 7) is False


def test_handle_rerank_error_ignores_unknown_exceptions() -> None:
    pipeline = _make_pipeline()
    assert pipeline._handle_rerank_error(ValueError("nope"), 7) is False
