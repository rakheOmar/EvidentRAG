from __future__ import annotations

import re
import uuid
from typing import Any

import pytest
from sqlalchemy import Select

from app.api.routes.threads import _build_answer_response
from app.infrastructure.db.models import (
    Answer,
    Document,
    Evidence,
    Message,
    Segment,
)

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32}",
    re.IGNORECASE,
)


class _AnswerGraphSession:
    def __init__(
        self, answer: Answer, evidence_by_id: dict[uuid.UUID, Evidence]
    ) -> None:
        self._answer = answer
        self._evidence_by_id = evidence_by_id

    async def scalar(self, statement: Select[Any]) -> object | None:
        compiled = statement.compile(compile_kwargs={"literal_binds": True})
        text = str(compiled)
        if "answers" in text:
            return self._answer
        match = _UUID_RE.search(text)
        if match and uuid.UUID(match.group(0)) in self._evidence_by_id:
            return self._evidence_by_id[uuid.UUID(match.group(0))]
        for value in compiled.params.values():
            if isinstance(value, uuid.UUID) and value in self._evidence_by_id:
                return self._evidence_by_id[value]
        return None

    async def scalars(self, statement: Select[Any]) -> object:
        compiled = statement.compile(compile_kwargs={"literal_binds": True})
        text = str(compiled)
        ids = {uuid.UUID(match.group(0)) for match in _UUID_RE.finditer(text)}
        return [
            evidence for evidence in self._evidence_by_id.values() if evidence.id in ids
        ]


class _NullAnswerSession:
    async def scalar(self, statement: object) -> None:
        return None


def _make_graph() -> tuple[
    Message, Answer, dict[uuid.UUID, Evidence], uuid.UUID, uuid.UUID, uuid.UUID
]:
    doc = Document(
        id=uuid.uuid4(),
        title="BERT Paper",
        slug="bert-paper",
        source_path="/corpus/bert.pdf",
        source_type="pdf",
        source_id=uuid.uuid4(),
        content_hash="h1",
        page_count=12,
    )
    ev_one = uuid.uuid4()
    ev_two = uuid.uuid4()
    missing = uuid.uuid4()
    evidence = {
        ev_one: Evidence(
            id=ev_one,
            document_id=doc.id,
            document=doc,
            locator="loc-1",
            content="BERT uses bidirectional transformers.",
            content_hash="c1",
            context_header="Section 1",
            page=1,
            chunk_index=0,
            token_count=10,
            extra={"asset_key": "assets/doc/1.png", "kind": "image"},
        ),
        ev_two: Evidence(
            id=ev_two,
            document_id=doc.id,
            document=doc,
            locator="loc-2",
            content="GLUE benchmarks measure language understanding.",
            content_hash="c2",
            context_header="Section 2",
            page=2,
            chunk_index=1,
            token_count=10,
            extra={},
        ),
    }
    answer = Answer(
        id=uuid.uuid4(),
        message_id=uuid.uuid4(),
        full_text="BERT improves language understanding.",
        reasoning_trace=[{"content": "step 1"}],
        extra={
            "evidence_metadata": {
                str(ev_one): {"erm_state": "boost", "erm_multiplier": 2.0}
            },
            "retrieved_evidence_ids": [str(ev_one), str(ev_two)],
        },
        segments=[
            Segment(
                id=uuid.uuid4(),
                answer_id=uuid.uuid4(),
                segment_index=0,
                text="BERT is bidirectional.",
                evidence_ids=[str(ev_one), str(ev_two), str(missing)],
                rating="up",
            ),
            Segment(
                id=uuid.uuid4(),
                answer_id=uuid.uuid4(),
                segment_index=1,
                text="It scores well on GLUE.",
                evidence_ids=[str(ev_two)],
                rating=None,
            ),
        ],
    )
    message = Message(id=answer.message_id, role="assistant")
    return message, answer, evidence, ev_one, ev_two, missing


@pytest.mark.asyncio
async def test_build_answer_response_returns_none_without_answer() -> None:
    message = Message(id=uuid.uuid4(), role="assistant")

    result = await _build_answer_response(_NullAnswerSession(), message)

    assert result is None


@pytest.mark.asyncio
async def test_build_answer_response_assembles_segments_evidence_and_erm_metadata() -> (
    None
):
    message, answer, evidence, ev_one, ev_two, missing = _make_graph()
    session = _AnswerGraphSession(answer, evidence)

    result = await _build_answer_response(session, message)

    assert result is not None
    assert result.full_text == answer.full_text
    assert result.reasoning_trace == [{"content": "step 1"}]
    assert len(result.segments) == 2

    # A referenced evidence id with no matching row is kept in the segment's
    # resolved list but never fetched into the evidence payload.
    assert len(result.segments[0].evidence_ids) == 3
    assert len(result.evidence) == 2
    evidence_ids_in_response = {str(ev.id) for ev in result.evidence}
    assert str(ev_one) in evidence_ids_in_response
    assert str(ev_two) in evidence_ids_in_response
    assert str(missing) not in evidence_ids_in_response

    # ERM boost/penalty metadata from answer.extra is projected onto the
    # matching EvidenceResponse.
    ev_one_response = next(ev for ev in result.evidence if str(ev.id) == str(ev_one))
    assert ev_one_response.erm_state == "boost"
    assert ev_one_response.erm_multiplier == 2.0
    assert ev_one_response.asset_url is not None
    assert ev_one_response.asset_url.endswith("/assets/1.png")

    assert isinstance(result.content_parts, list)
