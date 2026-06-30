from __future__ import annotations

from app.core.config import DatabaseSettings
from app.infrastructure.db.models import Document, Evidence
from app.infrastructure.db.session import create_engine


def test_document_table_columns_match_schema() -> None:
    cols = {c.name: c for c in Document.__table__.c}

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
    cols = {c.name: c for c in Evidence.__table__.c}

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
