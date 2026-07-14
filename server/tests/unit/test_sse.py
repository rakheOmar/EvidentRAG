from __future__ import annotations

import pytest

from app.api.sse.sse import redis_pubsub_stream, sse_event


def test_sse_event_formats_single_event() -> None:
    assert sse_event("done", {"status": "completed"}) == (
        'event: done\ndata: {"status":"completed"}\n\n'
    )


def test_sse_event_formats_nested_done_payload() -> None:
    assert sse_event(
        "done",
        {
            "id": "answer-1",
            "query_id": "query-1",
            "full_text": "First sentence. Second sentence.",
            "sentences": [
                {
                    "sentence_index": 0,
                    "sentence_text": "First sentence.",
                    "evidence_ids": ["e2"],
                }
            ],
            "evidence": [{"id": "e2", "content": "second evidence chunk"}],
        },
    ) == (
        'event: done\ndata: {"id":"answer-1","query_id":"query-1","full_text":"First sentence. Second sentence.","sentences":[{"sentence_index":0,"sentence_text":"First sentence.","evidence_ids":["e2"]}],"evidence":[{"id":"e2","content":"second evidence chunk"}]}\n\n'
    )


@pytest.mark.asyncio
async def test_redis_pubsub_stream_yields_events_until_done() -> None:
    class FakePubSub:
        def __init__(self) -> None:
            self.subscribed_channel: str | None = None
            self.unsubscribed_channel: str | None = None
            self.closed = False

        async def subscribe(self, channel: str) -> None:
            self.subscribed_channel = channel

        async def listen(self):
            for message in (
                {"type": "subscribe", "data": 1},
                {
                    "type": "message",
                    "data": '{"event":"route_selected","data":{"route":"simple"}}',
                },
                {
                    "type": "message",
                    "data": '{"event":"done","data":{"id":"answer-1","query_id":"query-1","full_text":"First sentence.","sentences":[{"sentence_index":0,"sentence_text":"First sentence.","evidence_ids":["e1"]}],"evidence":[{"id":"e1","content":"evidence chunk"}]}}',
                },
            ):
                yield message

        async def unsubscribe(self, channel: str) -> None:
            self.unsubscribed_channel = channel

        async def aclose(self) -> None:
            self.closed = True

    class FakeRedis:
        def __init__(self) -> None:
            self.instance = FakePubSub()

        def pubsub(self) -> FakePubSub:
            return self.instance

    redis = FakeRedis()

    events = [event async for event in redis_pubsub_stream(redis, "query:test:events")]

    assert events == [
        'event: route_selected\ndata: {"route":"simple"}\n\n',
        'event: done\ndata: {"id":"answer-1","query_id":"query-1","full_text":"First sentence.","sentences":[{"sentence_index":0,"sentence_text":"First sentence.","evidence_ids":["e1"]}],"evidence":[{"id":"e1","content":"evidence chunk"}]}\n\n',
    ]
    assert redis.instance.subscribed_channel == "query:test:events"
    assert redis.instance.unsubscribed_channel == "query:test:events"
    assert redis.instance.closed is True


@pytest.mark.asyncio
async def test_redis_pubsub_stream_subscribes_before_terminal_replay() -> None:
    calls: list[str] = []

    class FakePubSub:
        async def subscribe(self, channel: str) -> None:
            calls.append(f"subscribe:{channel}")

        async def listen(self):
            raise AssertionError("A terminal replay must not start listening.")
            yield

        async def unsubscribe(self, channel: str) -> None:
            calls.append(f"unsubscribe:{channel}")

        async def aclose(self) -> None:
            calls.append("close")

    class FakeRedis:
        def pubsub(self) -> FakePubSub:
            return FakePubSub()

    async def replay_terminal() -> tuple[list[str], bool]:
        calls.append("replay")
        return [sse_event("done", {"status": "completed"})], True

    events = [
        event
        async for event in redis_pubsub_stream(
            FakeRedis(),
            "query:test:events",
            after_subscribe=replay_terminal,
        )
    ]

    assert events == ['event: done\ndata: {"status":"completed"}\n\n']
    assert calls == [
        "subscribe:query:test:events",
        "replay",
        "unsubscribe:query:test:events",
        "close",
    ]
