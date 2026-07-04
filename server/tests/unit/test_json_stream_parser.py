from __future__ import annotations


def test_json_stream_parser_emits_completed_sentences_and_parses_final_output() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    chunks = [
        '[{"sentence":"First sentence.","evidence_ids":["e1"]},',
        '{"sentence":"Second sentence.","evidence_ids":["e2","e3"]}]',
    ]

    emitted_sentences: list[str] = []
    for chunk in chunks:
        emitted_sentences.extend(parser.feed(chunk))

    assert emitted_sentences == ["First sentence.", "Second sentence."]
    assert parser.parse_final() == [
        {"sentence": "First sentence.", "evidence_ids": ["e1"]},
        {"sentence": "Second sentence.", "evidence_ids": ["e2", "e3"]},
    ]


def test_json_stream_parser_ignores_incomplete_sentence_until_it_closes() -> None:
    from app.application.query_pipeline.json_stream_parser import JsonStreamParser

    parser = JsonStreamParser()

    assert parser.feed('[{"sentence":"Incomplete') == []
    assert parser.feed(' sentence.","evidence_ids":["e1"]}]') == [
        "Incomplete sentence."
    ]
