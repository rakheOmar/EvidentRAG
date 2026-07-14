"""Add document lifecycle integrity constraints."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260714_02"
down_revision = "20260711_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_documents_storage_key", "documents", ["storage_key"]
    )
    op.create_unique_constraint(
        "uq_documents_source_version",
        "documents",
        ["source_id", "version_number"],
    )
    op.create_index(
        "uq_documents_current_source",
        "documents",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_current_source", table_name="documents")
    op.drop_constraint("uq_documents_source_version", "documents", type_="unique")
    op.drop_constraint("uq_documents_storage_key", "documents", type_="unique")
