from datetime import datetime, timezone
from uuid import uuid4

from app.api.schemas.documents import DocumentResponse


def test_document_response_exposes_document_id_for_upload_contract() -> None:
    document_id = uuid4()
    response = DocumentResponse(
        id=document_id,
        document_id=document_id,
        source_id=uuid4(),
        source_key="source-key",
        title="Document",
        version_number=1,
        status="queued",
        is_current=False,
        original_filename="document.pdf",
        page_count=0,
        byte_size=12,
        error_message=None,
        created_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
        updated_at=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )

    assert response.document_id == document_id
    assert response.model_dump(mode="json")["document_id"] == str(document_id)
