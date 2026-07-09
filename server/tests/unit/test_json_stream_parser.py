from __future__ import annotations


def test_emits_completed_segment_texts_and_parses_final() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    chunks = [
        '[{"text":"First.","evidence_ids":["e1"]},',
        '{"text":"Second.","evidence_ids":["e2","e3"]}]',
    ]

    emitted: list[str] = []
    for chunk in chunks:
        emitted.extend(parser.feed(chunk))

    assert emitted == ["First.", "Second."]
    assert parser.parse_final() == [
        {"text": "First.", "evidence_ids": ["e1"]},
        {"text": "Second.", "evidence_ids": ["e2", "e3"]},
    ]


def test_parse_final_handles_leading_preamble() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed('Here is your summary:\n[{"text":"First.","evidence_ids":["e1"]}]')

    assert parser.parse_final() == [{"text": "First.", "evidence_ids": ["e1"]}]


def test_parse_final_handles_markdown_code_fences() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed('```json\n[{"text":"First.","evidence_ids":["e1"]}]\n```')

    assert parser.parse_final() == [{"text": "First.", "evidence_ids": ["e1"]}]


def test_parse_final_handles_trailing_text() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed('[{"text":"First.","evidence_ids":["e1"]}] I hope this helps')

    assert parser.parse_final() == [{"text": "First.", "evidence_ids": ["e1"]}]


def test_parse_final_returns_empty_for_non_json_output() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed("BERT and attention are closely related concepts.")

    assert parser.parse_final() == []


def test_ignores_incomplete_segment_until_it_closes() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    assert parser.feed('[{"text":"Incomplete') == []
    assert parser.feed(' complete.","evidence_ids":["e1"]}]') == [
        "Incomplete complete."
    ]


def test_get_accumulated_text_joins_all_segment_texts() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed(
        '[{"text":"First.","evidence_ids":[]},{"text":"Second.","evidence_ids":[]}]'
    )

    assert parser.get_accumulated_text() == "First. Second."


def test_get_accumulated_text_includes_partial_tokens() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    parser.feed('[{"text":"Hel')
    assert parser.get_accumulated_text() == "Hel"

    parser.feed('lo world.","evidence_ids":["e1"]}]')
    assert parser.get_accumulated_text() == "Hello world."


def test_get_accumulated_text_combines_completed_with_partial() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    parser.feed(
        '[{"text":"RAG stands for Retrieval Augmented Generation.","evidence_ids":["e1"]},'
    )
    assert (
        parser.get_accumulated_text()
        == "RAG stands for Retrieval Augmented Generation."
    )

    parser.feed('{"text":"It combines retriev')
    assert (
        parser.get_accumulated_text()
        == "RAG stands for Retrieval Augmented Generation. It combines retriev"
    )

    parser.feed('al with generation.","evidence_ids":["e2"]}]')
    assert (
        parser.get_accumulated_text()
        == "RAG stands for Retrieval Augmented Generation. It combines retrieval with generation."
    )


def test_get_accumulated_text_handles_json_escaped_chars() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed('[{"text":"Line1\\nLine2.","evidence_ids":[]}]')

    assert parser.get_accumulated_text() == "Line1\nLine2."


def test_get_accumulated_text_handles_space_after_colon() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    parser.feed('[{"text": "Hel')
    assert parser.get_accumulated_text() == "Hel"

    parser.feed('lo world.","evidence_ids":["e1"]}]')
    assert parser.get_accumulated_text() == "Hello world."


# --- get_segments() ---


def test_get_segments_returns_empty_before_any_feeds() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    assert parser.get_segments() == []


def test_get_segments_returns_completed_segments() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed(
        '[{"text":"One.","evidence_ids":["e1"]},'
        '{"text":"Two.","evidence_ids":["e2","e3"]}]'
    )

    assert parser.get_segments() == [
        {"text": "One.", "evidence_ids": ["e1"]},
        {"text": "Two.", "evidence_ids": ["e2", "e3"]},
    ]


def test_get_segments_excludes_partial_last_segment() -> None:
    """The last segment whose evidence_ids haven't arrived yet is still returned with empty evidence_ids."""
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    parser.feed('[{"text":"Complete.","evidence_ids":["e1"]},')
    assert parser.get_segments() == [
        {"text": "Complete.", "evidence_ids": ["e1"]},
    ]

    parser.feed('{"text":"Partial')
    assert parser.get_segments() == [
        {"text": "Complete.", "evidence_ids": ["e1"]},
    ]


def test_get_segments_includes_partial_segment_with_empty_ids_when_text_is_known() -> (
    None
):
    """Once text of a segment is complete but evidence_ids not yet, include it with empty evidence_ids."""
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    parser.feed('[{"text":"Only text here.","evidence_ids":')
    segments = parser.get_segments()
    assert segments[-1] == {"text": "Only text here.", "evidence_ids": []}


def test_get_segments_updates_partial_segment_when_ids_arrive() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    parser.feed('[{"text":"Cited text.","evidence_ids":["e1')
    segments = parser.get_segments()
    assert segments[-1] == {"text": "Cited text.", "evidence_ids": []}

    parser.feed('","e2"]}]')
    segments = parser.get_segments()
    assert segments[-1] == {"text": "Cited text.", "evidence_ids": ["e1", "e2"]}


def test_get_segments_handles_space_after_colon() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()
    parser.feed(
        '[{"text": "BERT stands for ", "evidence_ids": []},'
        '{"text": "Bidirectional Encoder", "evidence_ids": ["id1"]}]'
    )

    assert parser.get_segments() == [
        {"text": "BERT stands for ", "evidence_ids": []},
        {"text": "Bidirectional Encoder", "evidence_ids": ["id1"]},
    ]
