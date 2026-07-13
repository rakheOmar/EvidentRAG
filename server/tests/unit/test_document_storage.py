from __future__ import annotations

from uuid import uuid4

import pytest

from app.infrastructure.storage.local import LocalDocumentStorage


def test_stores_and_reads_original_document(tmp_path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))
    document_id = uuid4()
    key = storage.key_for_original(document_id, "policy.pdf")

    storage.write(key, b"%PDF-1.7")

    assert key == f"originals/{document_id}.pdf"
    assert storage.read(key) == b"%PDF-1.7"


def test_rejects_storage_key_outside_root(tmp_path) -> None:
    storage = LocalDocumentStorage(str(tmp_path))

    with pytest.raises(ValueError, match="escapes"):
        storage.path("../outside.pdf")
