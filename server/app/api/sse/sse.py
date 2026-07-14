from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def redis_pubsub_stream(
    redis,
    channel: str,
    after_subscribe: Callable[[], Awaitable[tuple[list[str], bool]]] | None = None,
) -> AsyncIterator[str]:
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    try:
        if after_subscribe is not None:
            initial_events, terminal = await after_subscribe()
            for event in initial_events:
                yield event
            if terminal:
                return

        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue

            raw_data = message.get("data")
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode("utf-8")

            payload = json.loads(raw_data)
            event_name = payload["event"]
            yield sse_event(event_name, payload["data"])

            if event_name in {"done", "error"}:
                break
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
