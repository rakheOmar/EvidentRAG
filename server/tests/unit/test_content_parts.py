from __future__ import annotations


def test_reasoning_part_returns_reasoning_message_part_shape() -> None:
    from app.application.query_pipeline.content_parts import reasoning_part

    result = reasoning_part("Routing Query via Simple Route...")

    assert result == {
        "type": "reasoning",
        "text": "Routing Query via Simple Route...",
    }


def test_text_part_returns_text_message_part_shape() -> None:
    from app.application.query_pipeline.content_parts import text_part

    result = text_part("HNSW stands for Hierarchical Navigable Small World.")

    assert result == {
        "type": "text",
        "text": "HNSW stands for Hierarchical Navigable Small World.",
    }


def test_source_part_returns_document_source_part_with_provider_metadata() -> None:
    from app.application.query_pipeline.content_parts import source_part

    evidence_row: dict[str, object] = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "content": "RAG is a technique that combines retrieval with generation.",
        "context_header": "Introduction",
        "document_title": "RAG Overview",
        "document_slug": "rag-overview",
        "page": 3,
    }

    result = source_part(evidence_row)

    assert result["type"] == "source"
    assert result["sourceType"] == "document"
    assert result["id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert result["title"] == "RAG Overview"
    assert result["mediaType"] == "text/plain"
    assert result["providerMetadata"] == {"evidentrag": evidence_row}
    assert result["filename"] == "rag-overview.txt"


def test_source_part_uses_locator_as_title_when_document_title_missing() -> None:
    from app.application.query_pipeline.content_parts import source_part

    evidence_row: dict[str, object] = {
        "id": "660e8400-e29b-41d4-a716-446655440001",
        "content": "Some evidence content.",
    }

    result = source_part(evidence_row)

    assert result["title"] == "Evidence 660e8400..."
    assert result["providerMetadata"] == {"evidentrag": evidence_row}


def test_source_part_includes_filename_when_provided() -> None:
    from app.application.query_pipeline.content_parts import source_part

    evidence_row: dict[str, object] = {
        "id": "770e8400-e29b-41d4-a716-446655440002",
        "content": "File evidence content.",
        "document_title": "My Document",
        "document_slug": "my-doc",
    }

    result = source_part(evidence_row)

    assert result["filename"] == "my-doc.txt"


def test_answer_content_parts_returns_text_then_sources() -> None:
    from app.application.query_pipeline.content_parts import (
        answer_content_parts,
        source_part,
    )

    evidence_rows: list[dict[str, object]] = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "content": "First evidence content.",
            "document_title": "Doc 1",
            "document_slug": "doc-1",
        },
        {
            "id": "660e8400-e29b-41d4-a716-446655440001",
            "content": "Second evidence content.",
            "document_title": "Doc 2",
            "document_slug": "doc-2",
        },
    ]
    full_text = "RAG combines retrieval with generation to ground LLM outputs."

    result = answer_content_parts(full_text, evidence_rows)

    assert result == [
        {"type": "text", "text": full_text},
        source_part(evidence_rows[0]),
        source_part(evidence_rows[1]),
    ]


def test_answer_content_parts_returns_text_only_when_no_evidence() -> None:
    from app.application.query_pipeline.content_parts import answer_content_parts

    result = answer_content_parts("Just text.", [])

    assert result == [{"type": "text", "text": "Just text."}]


def test_answer_content_parts_removes_model_authored_image_markdown() -> None:
    from app.application.query_pipeline.content_parts import answer_content_parts

    result = answer_content_parts(
        "See ![Figure 2](#) for the input representation.",
        [],
    )

    assert result == [{"type": "text", "text": "See  for the input representation."}]
