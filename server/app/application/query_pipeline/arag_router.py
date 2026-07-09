from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from time import perf_counter

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """\
You are an adaptive query router for a RAG system. Classify the user's query into one of these routes:

- "simple": Factual, single-step questions. "What is X?" or "How does X work?"
- "multi_hop": Multi-step reasoning requiring iterative retrieval. "What causes X, and how does that lead to Y?"
- "comparison": Questions comparing two or more entities. "Compare X and Y" or "What are the differences between X and Y?"
- "aggregation": Broad overview or summary questions. "Tell me about the main themes" or "Summarize the document"
- "conversation": Questions about the conversation itself, prior turns, what the user or assistant previously said, or requests to restate thread history.

For "multi_hop" and "comparison" routes, also decompose the query into sub-queries that retrieve for individual steps or entities.
For "aggregation", generate diverse reformulations that help retrieve broad coverage of the topic.
For "conversation", use [] for sub_queries because the answer should come from thread memory rather than retrieval.

Return a JSON object with:
- "route": one of "simple", "multi_hop", "comparison", "aggregation", "conversation"
- "sub_queries": an array of strings. Use [] for "simple". Use decomposed or reformulated sub-queries for the other routes when they help retrieval.
"""


@dataclass
class RoutingResult:
    route: str = "simple"
    sub_queries: list[str] = field(default_factory=list)


class AragRouter:
    def __init__(self, llm_client) -> None:
        self._llm_client = llm_client

    async def classify(
        self, query_text: str, model: str | None = None
    ) -> RoutingResult:
        started_at = perf_counter()
        wide_event: dict[str, object] = {
            "event": "arag_router_classify",
            "query_text": query_text,
        }

        messages = [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": query_text},
        ]

        try:
            raw = await self._llm_client.generate(messages, model=model)
            parsed = json.loads(raw)
            route = str(parsed.get("route", "simple")).lower()
            if route not in (
                "simple",
                "multi_hop",
                "comparison",
                "aggregation",
                "conversation",
            ):
                wide_event["invalid_route"] = route
                route = "simple"
            sub_queries = [
                str(sq) for sq in parsed.get("sub_queries", []) if isinstance(sq, str)
            ]
            wide_event["route"] = route
            wide_event["sub_queries"] = sub_queries
            wide_event["outcome"] = "success"
            return RoutingResult(route=route, sub_queries=sub_queries)
        except Exception as exc:
            wide_event["outcome"] = "error"
            wide_event["error_type"] = type(exc).__name__
            wide_event["error_message"] = str(exc)
            return RoutingResult(route="simple", sub_queries=[])
        finally:
            wide_event["duration_ms"] = round((perf_counter() - started_at) * 1000, 2)
            logger.info("arag_router_classify", extra={"wide_event": wide_event})
