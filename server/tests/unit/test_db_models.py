from __future__ import annotations

from typing import cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint

from app.core.config import DatabaseSettings
from app.infrastructure.db.models import (
    Answer,
    Base,
    Document,
    Evidence,
    Message,
    MessageEvidenceCandidate,
    Segment,
    Thread,
)
from app.infrastructure.db.session import create_engine


def _table(model: type[Base]) -> Table:
    return cast(Table, model.__table__)


def _check_constraints(table: Table) -> list[CheckConstraint]:
    return [
        cast(CheckConstraint, constraint)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    ]


def _unique_constraints(table: Table) -> list[UniqueConstraint]:
    return [
        cast(UniqueConstraint, constraint)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]


def test_document_table_columns_match_schema() -> None:
    cols = {c.name: c for c in _table(Document).c}

    assert Document.__tablename__ == "documents"
    assert str(cols["id"].type) == "UUID"
    assert cols["id"].primary_key
    assert len(cols) == 10


def test_evidence_table_columns_match_schema() -> None:
    cols = {c.name: c for c in _table(Evidence).c}

    assert Evidence.__tablename__ == "evidence"
    assert str(cols["id"].type) == "UUID"
    assert cols["id"].primary_key
    assert len(cols) == 12


def test_thread_table_columns_match_schema() -> None:
    cols = {c.name: c for c in _table(Thread).c}

    assert Thread.__tablename__ == "threads"
    assert str(cols["id"].type) == "UUID"
    assert cols["id"].primary_key
    assert str(cols["title"].type) == "TEXT"
    assert not cols["title"].nullable
    assert str(cols["summary"].type) == "TEXT"
    assert not cols["summary"].nullable
    assert len(cols) == 6


def test_message_table_columns_match_schema() -> None:
    table = _table(Message)
    cols = {c.name: c for c in table.c}

    assert Message.__tablename__ == "messages"
    assert str(cols["thread_id"].type) == "UUID"
    assert str(cols["position"].type) == "INTEGER"
    assert str(cols["role"].type) == "TEXT"
    assert str(cols["status"].type) == "TEXT"
    assert str(cols["sub_queries"].type) == "JSONB"
    assert str(cols["reply_to_message_id"].type) == "UUID"

    checks = _check_constraints(table)
    assert any("role" in str(constraint.sqltext) for constraint in checks)
    assert any("status" in str(constraint.sqltext) for constraint in checks)

    unique_constraints = _unique_constraints(table)
    assert any(
        tuple(column.name for column in constraint.columns) == ("thread_id", "position")
        for constraint in unique_constraints
    )

    assert len(cols) == 14


def test_answer_table_columns_match_schema() -> None:
    cols = {c.name: c for c in _table(Answer).c}

    assert Answer.__tablename__ == "answers"
    assert str(cols["message_id"].type) == "UUID"
    assert not cols["message_id"].nullable
    assert cols["message_id"].unique
    assert len(cols) == 8


def test_segment_table_columns_match_schema() -> None:
    table = _table(Segment)
    cols = {c.name: c for c in table.c}

    assert Segment.__tablename__ == "segments"
    assert str(cols["answer_id"].type) == "UUID"
    unique_constraints = _unique_constraints(table)
    assert any(
        tuple(column.name for column in constraint.columns)
        == ("answer_id", "segment_index")
        for constraint in unique_constraints
    )


def test_message_evidence_candidate_table_columns_match_schema() -> None:
    table = _table(MessageEvidenceCandidate)
    cols = {c.name: c for c in table.c}

    assert MessageEvidenceCandidate.__tablename__ == "message_evidence_candidates"
    assert str(cols["message_id"].type) == "UUID"
    assert cols["message_id"].primary_key
    checks = _check_constraints(table)
    assert any("stage" in str(constraint.sqltext) for constraint in checks)
    unique_constraints = _unique_constraints(table)
    assert any(
        tuple(column.name for column in constraint.columns)
        == ("message_id", "stage", "rank")
        for constraint in unique_constraints
    )


def test_create_engine_uses_correct_url() -> None:
    settings = DatabaseSettings(
        host="pg.example.com",
        port=5433,
        user="admin",
        password="secret",
        db="ragdb",
    )

    engine = create_engine(settings)

    assert engine.url.drivername == "postgresql+asyncpg"
    assert engine.url.host == "pg.example.com"
    assert engine.url.port == 5433
    assert engine.url.username == "admin"
    assert engine.url.password == "secret"
    assert engine.url.database == "ragdb"
