from __future__ import annotations

import re


_MODEL_IMAGE_MARKDOWN = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def reasoning_part(text: str) -> dict[str, object]:
    return {"type": "reasoning", "text": text}


def text_part(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


def source_part(evidence_row: dict[str, object]) -> dict[str, object]:
    evidence_id = str(evidence_row["id"])
    source: dict[str, object] = {
        "type": "source",
        "sourceType": "document",
        "id": evidence_id,
        "title": evidence_row.get(
            "document_title",
            f"Evidence {evidence_id[:8]}...",
        ),
        "mediaType": (
            "image/png" if evidence_row.get("kind") == "visual" else "text/plain"
        ),
        "providerMetadata": {"evidentrag": evidence_row},
    }
    doc_slug = evidence_row.get("document_slug")
    if doc_slug:
        source["filename"] = f"{doc_slug}.txt"
    return source


def answer_content_parts(
    full_text: str,
    evidence_list: list[dict[str, object]],
) -> list[dict[str, object]]:
    clean_text = _MODEL_IMAGE_MARKDOWN.sub("", full_text)
    parts: list[dict[str, object]] = [text_part(clean_text)]
    for ev in evidence_list:
        if ev.get("kind") == "visual" and ev.get("asset_url"):
            parts.append(
                {
                    "type": "image",
                    "image": ev["asset_url"],
                    "filename": ev.get("document_title", "Retrieved image"),
                }
            )
        parts.append(source_part(ev))
    return parts
