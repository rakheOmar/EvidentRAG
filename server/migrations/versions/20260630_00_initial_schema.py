"""Create the initial EvidentRAG persistence schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260630_00"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("source_path", sa.Text(), nullable=False, unique=True),
        sa.Column("source_type", sa.Text(), nullable=False, server_default="pdf"),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("locator", sa.Text(), nullable=False, unique=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("context_header", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_evidence_doc_chunk"),
    )
    op.create_table(
        "threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reply_to_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("selected_route", sa.Text()),
        sa.Column(
            "sub_queries", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column("error_message", sa.Text()),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        *_timestamps(),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_messages_status",
        ),
        sa.UniqueConstraint(
            "thread_id", "position", name="uq_messages_thread_position"
        ),
    )
    op.create_table(
        "answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column(
            "reasoning_trace",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("model_name", sa.Text()),
        sa.Column("prompt_version", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_table(
        "segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "answer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("answers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False),
        sa.Column("rating", sa.Text()),
        sa.UniqueConstraint(
            "answer_id", "segment_index", name="uq_segments_answer_index"
        ),
        sa.CheckConstraint(
            "rating IS NULL OR rating IN ('up', 'down')",
            name="ck_segments_rating",
        ),
    )
    op.create_table(
        "message_evidence_candidates",
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stage", sa.Text(), primary_key=True),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", postgresql.DOUBLE_PRECISION()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "message_id",
            "stage",
            "rank",
            name="uq_message_evidence_candidates_message_stage_rank",
        ),
        sa.CheckConstraint(
            "stage IN ('dense', 'sparse', 'fused', 'reranked', 'selected')",
            name="ck_message_evidence_candidates_stage",
        ),
    )
    op.create_table(
        "erm_query_embeddings",
        sa.Column("query_embedding_hash", sa.Text(), primary_key=True),
        sa.Column("embedding", postgresql.JSONB(), nullable=False, server_default="[]"),
        *_timestamps(),
    )
    op.create_table(
        "erm_scores",
        sa.Column(
            "query_embedding_hash",
            sa.Text(),
            sa.ForeignKey(
                "erm_query_embeddings.query_embedding_hash", ondelete="CASCADE"
            ),
            primary_key=True,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "boost_score",
            postgresql.DOUBLE_PRECISION(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "penalty_score",
            postgresql.DOUBLE_PRECISION(),
            nullable=False,
            server_default="0",
        ),
        *_timestamps(),
    )


def downgrade() -> None:
    for table in (
        "erm_scores",
        "erm_query_embeddings",
        "message_evidence_candidates",
        "segments",
        "answers",
        "messages",
        "threads",
        "evidence",
        "documents",
    ):
        op.drop_table(table)
