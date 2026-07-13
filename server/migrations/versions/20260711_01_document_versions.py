"""Add Source and versioned document lifecycle."""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260711_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_key", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    fields = (
        ("source_id", postgresql.UUID(as_uuid=True)),
        ("version_number", sa.Integer()),
        ("status", sa.Text()),
        ("is_current", sa.Boolean()),
        ("storage_key", sa.Text()),
        ("original_filename", sa.Text()),
        ("content_type", sa.Text()),
        ("byte_size", sa.Integer()),
        ("error_message", sa.Text()),
        ("warnings", postgresql.JSONB()),
        ("canonical_document_id", postgresql.UUID(as_uuid=True)),
    )
    for name, column in fields:
        op.add_column("documents", sa.Column(name, column, nullable=True))
    bind = op.get_bind()
    for row in bind.execute(sa.text("SELECT id, title FROM documents")).mappings():
        source_id = uuid.uuid4()
        bind.execute(
            sa.text(
                "INSERT INTO sources (id, source_key, title) VALUES (:id, :key, :title)"
            ),
            {"id": source_id, "key": f"legacy:{row['id']}", "title": row["title"]},
        )
        bind.execute(
            sa.text(
                "UPDATE documents SET source_id=:source_id, version_number=1, status='ready', is_current=true, warnings='[]'::jsonb WHERE id=:id"
            ),
            {"source_id": source_id, "id": row["id"]},
        )
    op.alter_column("documents", "source_id", nullable=False)
    op.alter_column("documents", "version_number", nullable=False, server_default="1")
    op.alter_column("documents", "status", nullable=False, server_default="pending")
    op.alter_column(
        "documents", "is_current", nullable=False, server_default=sa.text("false")
    )
    op.alter_column("documents", "warnings", nullable=False, server_default="[]")
    op.create_foreign_key(
        "fk_documents_source",
        "documents",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_documents_canonical",
        "documents",
        "documents",
        ["canonical_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for name in ("source_id", "status", "is_current"):
        op.create_index(f"ix_documents_{name}", "documents", [name])


def downgrade() -> None:
    for name in ("is_current", "status", "source_id"):
        op.drop_index(f"ix_documents_{name}", table_name="documents")
    op.drop_constraint("fk_documents_canonical", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_source", "documents", type_="foreignkey")
    for name in (
        "canonical_document_id",
        "warnings",
        "error_message",
        "byte_size",
        "content_type",
        "original_filename",
        "storage_key",
        "is_current",
        "status",
        "version_number",
        "source_id",
    ):
        op.drop_column("documents", name)
    op.drop_table("sources")
