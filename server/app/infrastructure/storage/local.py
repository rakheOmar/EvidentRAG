from __future__ import annotations

from pathlib import Path
from uuid import UUID


class LocalDocumentStorage:
    """Filesystem-backed storage for original and derived document assets."""

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()

    def key_for_original(self, document_id: UUID, filename: str) -> str:
        suffix = Path(filename).suffix.lower() or ".pdf"
        return f"originals/{document_id}{suffix}"

    def write(self, key: str, content: bytes) -> Path:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def path(self, key: str) -> Path:
        candidate = (self._root / key).resolve()
        if candidate != self._root and self._root not in candidate.parents:
            raise ValueError("Storage key escapes document storage root")
        return candidate
