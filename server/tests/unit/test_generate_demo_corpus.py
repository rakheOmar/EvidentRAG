from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typing import Any

from app.seed.generate_demo_corpus import generate_demo_corpus


class _FakeOrigin:
    def __init__(self, page_no: int) -> None:
        self.page_no = page_no


class _FakeMeta:
    def __init__(self, page_no: int, *, include_origin: bool = True) -> None:
        self.origin = _FakeOrigin(page_no)
        self.doc_items = []
        if not include_origin:
            self.origin = object()
            self.doc_items = [_FakeDocItem(page_no)]


class _FakeProv:
    def __init__(self, page_no: int) -> None:
        self.page_no = page_no


class _FakeDocItem:
    def __init__(self, page_no: int) -> None:
        self.prov = [_FakeProv(page_no)]


class _FakeChunk:
    def __init__(self, text: str, page_no: int, *, include_origin: bool = True) -> None:
        self.text = text
        self.meta = _FakeMeta(page_no, include_origin=include_origin)


class _FakeResult:
    def __init__(self, document: object) -> None:
        self.document = document


class _FakeConverter:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def convert(self, source: str | Path) -> _FakeResult:
        return _FakeResult(
            {
                "name": Path(source).stem,
                "title": "Attention Is All You Need",
                "page_count": 15,
            }
        )


class _FakeChunker:
    def chunk(self, document: object) -> list[_FakeChunk]:
        return [
            _FakeChunk("Transformers rely on attention.", 1),
            _FakeChunk("The decoder attends to encoder outputs.", 2),
        ]


class _FallbackPageChunker:
    def chunk(self, document: object) -> list[_FakeChunk]:
        return [_FakeChunk("Transformers rely on attention.", 1, include_origin=False)]


def test_generate_demo_corpus_disables_pdf_ocr(monkeypatch, tmp_path) -> None:
    source_dir = tmp_path / "corpus"
    output_dir = tmp_path / "demo-corpus"
    source_dir.mkdir()
    (source_dir / "attention-is-all-you-need-arxiv-1706.03762.pdf").write_bytes(
        b"fake-pdf-bytes"
    )

    captured: dict[str, Any] = {}

    class CapturingConverter(_FakeConverter):
        def __init__(self, **kwargs) -> None:
            super().__init__(**kwargs)
            captured.update(kwargs)

    monkeypatch.setattr(
        "app.seed.generate_demo_corpus.DocumentConverter", CapturingConverter
    )
    monkeypatch.setattr(
        "app.seed.generate_demo_corpus.HybridChunker", lambda: _FakeChunker()
    )

    generate_demo_corpus(source_dir, output_dir)

    format_options = captured["format_options"]
    pdf_option = next(iter(format_options.values()))
    assert pdf_option.pipeline_options.do_ocr is False
    assert pdf_option.pipeline_options.do_table_structure is False


def test_generate_demo_corpus_uses_doc_item_provenance_for_page(monkeypatch, tmp_path) -> None:
    source_dir = tmp_path / "corpus"
    output_dir = tmp_path / "demo-corpus"
    source_dir.mkdir()
    (source_dir / "attention-is-all-you-need-arxiv-1706.03762.pdf").write_bytes(
        b"fake-pdf-bytes"
    )

    monkeypatch.setattr(
        "app.seed.generate_demo_corpus.DocumentConverter", _FakeConverter
    )
    monkeypatch.setattr(
        "app.seed.generate_demo_corpus.HybridChunker", lambda: _FallbackPageChunker()
    )

    written_files = generate_demo_corpus(source_dir, output_dir)

    payload = json.loads(written_files[0].read_text())
    assert payload["evidence"][0]["page"] == 1
    assert payload["evidence"][0]["locator"].endswith("-p1-c0")


def test_generate_demo_corpus_writes_normalized_json(monkeypatch, tmp_path) -> None:
    source_dir = tmp_path / "corpus"
    output_dir = tmp_path / "demo-corpus"
    source_dir.mkdir()
    pdf_path = source_dir / "attention-is-all-you-need-arxiv-1706.03762.pdf"
    pdf_path.write_bytes(b"fake-pdf-bytes")

    monkeypatch.setattr(
        "app.seed.generate_demo_corpus.DocumentConverter", _FakeConverter
    )
    monkeypatch.setattr(
        "app.seed.generate_demo_corpus.HybridChunker", lambda: _FakeChunker()
    )

    written_files = generate_demo_corpus(source_dir, output_dir)
    document_hash = hashlib.sha256(b"fake-pdf-bytes").hexdigest()
    first_chunk_hash = hashlib.sha256(
        b"Transformers rely on attention."
    ).hexdigest()
    second_chunk_hash = hashlib.sha256(
        b"The decoder attends to encoder outputs."
    ).hexdigest()

    assert written_files == [
        output_dir / "attention-is-all-you-need-arxiv-1706-03762.json"
    ]

    payload = json.loads(written_files[0].read_text())
    assert payload == {
        "document": {
            "title": "Attention Is All You Need",
            "slug": "attention-is-all-you-need-arxiv-1706-03762",
            "source_path": "corpus/attention-is-all-you-need-arxiv-1706.03762.pdf",
            "source_type": "pdf",
            "content_hash": document_hash,
            "page_count": 15,
            "metadata": {},
        },
        "evidence": [
            {
                "locator": "attention-is-all-you-need-arxiv-1706-03762-p1-c0",
                "content": "Transformers rely on attention.",
                "content_hash": first_chunk_hash,
                "context_header": "Passage from Attention Is All You Need, page 1.",
                "page": 1,
                "chunk_index": 0,
                "token_count": 4,
                "metadata": {},
            },
            {
                "locator": "attention-is-all-you-need-arxiv-1706-03762-p2-c1",
                "content": "The decoder attends to encoder outputs.",
                "content_hash": second_chunk_hash,
                "context_header": "Passage from Attention Is All You Need, page 2.",
                "page": 2,
                "chunk_index": 1,
                "token_count": 6,
                "metadata": {},
            },
        ],
    }
