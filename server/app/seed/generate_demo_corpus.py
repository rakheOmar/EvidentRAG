from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from collections.abc import Sequence

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _document_title(document: object, pdf_path: Path) -> str:
    if isinstance(document, dict):
        return str(document.get("title") or document.get("name") or pdf_path.stem)

    title = getattr(document, "title", None) or getattr(document, "name", None)
    if title:
        return str(title)

    origin = getattr(document, "origin", None)
    if origin is not None:
        origin_title = getattr(origin, "title", None) or getattr(
            origin, "filename", None
        )
        if origin_title:
            return str(origin_title)

    return pdf_path.stem


def _document_page_count(document: object, chunks: Sequence[Any]) -> int:
    if isinstance(document, dict) and isinstance(document.get("page_count"), int):
        return document["page_count"]

    page_count = getattr(document, "page_count", None)
    if isinstance(page_count, int):
        return page_count

    pages = {_chunk_page(chunk) for chunk in chunks}
    return len({page for page in pages if isinstance(page, int)})


def _chunk_page(chunk: Any) -> int | None:
    origin = getattr(getattr(chunk, "meta", None), "origin", None)
    page_no = getattr(origin, "page_no", None)
    if isinstance(page_no, int):
        return page_no

    for doc_item in getattr(getattr(chunk, "meta", None), "doc_items", []):
        for prov in getattr(doc_item, "prov", []):
            page_no = getattr(prov, "page_no", None)
            if isinstance(page_no, int):
                return page_no

    return None


def _create_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def generate_demo_corpus(source_dir: Path, output_dir: Path) -> list[Path]:
    converter = _create_converter()
    chunker = HybridChunker()
    output_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []
    for pdf_path in sorted(source_dir.glob("*.pdf")):
        result = converter.convert(str(pdf_path))
        chunks = list(chunker.chunk(result.document))

        title = _document_title(result.document, pdf_path)
        slug = _slugify(pdf_path.stem)
        source_path = f"{source_dir.name}/{pdf_path.name}"

        evidence = []
        for chunk_index, chunk in enumerate(chunks):
            page = _chunk_page(chunk)
            if not isinstance(page, int):
                raise ValueError(
                    f"Missing page number for chunk {chunk_index} in {pdf_path.name}"
                )

            evidence.append(
                {
                    "locator": f"{slug}-p{page}-c{chunk_index}",
                    "content": chunk.text,
                    "content_hash": _sha256_text(chunk.text),
                    "context_header": f"Passage from {title}, page {page}.",
                    "page": page,
                    "chunk_index": chunk_index,
                    "token_count": len(chunk.text.split()),
                    "metadata": {},
                }
            )

        payload = {
            "document": {
                "title": title,
                "slug": slug,
                "source_path": source_path,
                "source_type": "pdf",
                "content_hash": _sha256_bytes(pdf_path.read_bytes()),
                "page_count": _document_page_count(result.document, chunks),
                "metadata": {},
            },
            "evidence": evidence,
        }

        output_path = output_dir / f"{slug}.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written_files.append(output_path)

    return written_files


def main() -> int:
    root_dir = Path(__file__).resolve().parents[3]
    source_dir = root_dir / "corpus"
    output_dir = root_dir / "server" / "app" / "seed" / "demo-corpus"
    generate_demo_corpus(source_dir, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
