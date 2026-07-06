from __future__ import annotations

from typing import cast

from sqlalchemy import CheckConstraint, Table, UniqueConstraint

from app.core.config import DatabaseSettings
from app.infrastructure.db.models import (
    Answer,
    Base,
    Document,
    Evidence,
    Query,
    QueryEvidenceCandidate,
    Segment,
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
    assert not cols["id"].nullable
    assert cols["id"].primary_key

    assert str(cols["title"].type) == "TEXT"
    assert not cols["title"].nullable

    assert str(cols["slug"].type) == "TEXT"
    assert not cols["slug"].nullable
    assert cols["slug"].unique

    assert str(cols["source_path"].type) == "TEXT"
    assert not cols["source_path"].nullable
    assert cols["source_path"].unique

    assert cols["source_type"].default is not None

    assert str(cols["content_hash"].type) == "TEXT"
    assert not cols["content_hash"].nullable

    assert str(cols["page_count"].type) == "INTEGER"
    assert not cols["page_count"].nullable

    assert str(cols["metadata"].type) == "JSONB"
    assert not cols["metadata"].nullable

    assert len(cols) == 10


def test_evidence_table_columns_match_schema() -> None:
    cols = {c.name: c for c in _table(Evidence).c}

    assert Evidence.__tablename__ == "evidence"
    assert str(cols["id"].type) == "UUID"
    assert cols["id"].primary_key

    assert str(cols["document_id"].type) == "UUID"
    assert not cols["document_id"].nullable

    assert str(cols["locator"].type) == "TEXT"
    assert not cols["locator"].nullable
    assert cols["locator"].unique

    assert str(cols["content"].type) == "TEXT"
    assert not cols["content"].nullable

    assert str(cols["content_hash"].type) == "TEXT"
    assert not cols["content_hash"].nullable

    assert str(cols["context_header"].type) == "TEXT"
    assert not cols["context_header"].nullable

    assert str(cols["page"].type) == "INTEGER"
    assert not cols["page"].nullable

    assert str(cols["chunk_index"].type) == "INTEGER"
    assert not cols["chunk_index"].nullable

    assert str(cols["token_count"].type) == "INTEGER"
    assert not cols["token_count"].nullable

    assert str(cols["metadata"].type) == "JSONB"
    assert not cols["metadata"].nullable

    assert len(cols) == 12


def test_query_table_columns_match_schema() -> None:
    table = _table(Query)
    cols = {c.name: c for c in table.c}

    assert Query.__tablename__ == "queries"
    assert str(cols["id"].type) == "UUID"
    assert cols["id"].primary_key

    assert str(cols["query_text"].type) == "TEXT"
    assert not cols["query_text"].nullable

    assert str(cols["selected_route"].type) == "TEXT"
    assert not cols["selected_route"].nullable
    assert cols["selected_route"].default is not None

    assert str(cols["status"].type) == "TEXT"
    assert not cols["status"].nullable
    assert cols["status"].default is not None

    assert str(cols["metadata"].type) == "JSONB"
    assert not cols["metadata"].nullable

    assert str(cols["error_message"].type) == "TEXT"
    assert cols["error_message"].nullable

    assert str(cols["completed_at"].type) == "TIMESTAMP"
    assert cols["completed_at"].nullable

    status_checks = _check_constraints(table)
    assert any("status" in str(constraint.sqltext) for constraint in status_checks)

    assert len(cols) == 9


def test_answer_table_columns_match_schema() -> None:
    cols = {c.name: c for c in _table(Answer).c}

    assert Answer.__tablename__ == "answers"
    assert str(cols["id"].type) == "UUID"
    assert cols["id"].primary_key

    assert str(cols["query_id"].type) == "UUID"
    assert not cols["query_id"].nullable
    assert cols["query_id"].unique

    assert str(cols["full_text"].type) == "TEXT"
    assert not cols["full_text"].nullable

    assert str(cols["model_name"].type) == "TEXT"
    assert cols["model_name"].nullable

    assert str(cols["prompt_version"].type) == "TEXT"
    assert cols["prompt_version"].nullable

    assert str(cols["metadata"].type) == "JSONB"
    assert not cols["metadata"].nullable

    assert str(cols["created_at"].type) == "TIMESTAMP"
    assert not cols["created_at"].nullable

    assert len(cols) == 7


def test_segment_table_columns_match_schema() -> None:
    table = _table(Segment)
    cols = {c.name: c for c in table.c}

    assert Segment.__tablename__ == "segments"
    assert str(cols["id"].type) == "UUID"
    assert cols["id"].primary_key

    assert str(cols["answer_id"].type) == "UUID"
    assert not cols["answer_id"].nullable

    assert str(cols["segment_index"].type) == "INTEGER"
    assert not cols["segment_index"].nullable

    assert str(cols["text"].type) == "TEXT"
    assert not cols["text"].nullable

    assert str(cols["evidence_ids"].type) == "JSONB"
    assert not cols["evidence_ids"].nullable

    unique_constraints = _unique_constraints(table)
    assert any(
        tuple(column.name for column in constraint.columns)
        == ("answer_id", "segment_index")
        for constraint in unique_constraints
    )

    assert len(cols) == 5


def test_query_evidence_candidate_table_columns_match_schema() -> None:
    table = _table(QueryEvidenceCandidate)
    cols = {c.name: c for c in table.c}

    assert QueryEvidenceCandidate.__tablename__ == "query_evidence_candidates"
    assert str(cols["query_id"].type) == "UUID"
    assert cols["query_id"].primary_key

    assert str(cols["stage"].type) == "TEXT"
    assert cols["stage"].primary_key

    assert str(cols["evidence_id"].type) == "UUID"
    assert cols["evidence_id"].primary_key

    assert str(cols["rank"].type) == "INTEGER"
    assert not cols["rank"].nullable

    assert str(cols["score"].type) == "DOUBLE PRECISION"
    assert cols["score"].nullable

    assert str(cols["metadata"].type) == "JSONB"
    assert not cols["metadata"].nullable

    assert str(cols["created_at"].type) == "TIMESTAMP"
    assert not cols["created_at"].nullable

    checks = _check_constraints(table)
    assert any("stage" in str(constraint.sqltext) for constraint in checks)

    unique_constraints = _unique_constraints(table)
    assert any(
        tuple(column.name for column in constraint.columns)
        == ("query_id", "stage", "rank")
        for constraint in unique_constraints
    )

    assert len(cols) == 7


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
    assert engine.dialect.name == "postgresql"
