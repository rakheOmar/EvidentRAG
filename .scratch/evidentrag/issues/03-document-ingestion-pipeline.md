Status: done

## What to build

The full async Document Ingestion Pipeline: a user uploads a PDF through the UI, the backend parses it with Docling, chunks text, adds deterministic structural Context Headers (CCH), captions images, embeds everything via Gemini Embedding 2, upserts vectors to Qdrant, stores metadata in PostgreSQL, and streams progress back to the UI. The user can view a list of all uploaded Documents with their processing status and delete Sources through auditable tombstones.

## Acceptance criteria

- [x] `POST /api/v1/documents` accepts multipart PDF upload, creates a Document resource, and returns `201 Created` with a `document_id`; invalid uploads return `400`, unsupported media returns `415`, and validation failures return `422`
- [x] Upload triggers async ingestion: parse PDF with Docling -> chunk text at paragraph boundaries -> add deterministic CCH from document title + section hierarchy -> caption images via Utility LLM -> embed via Gemini Embedding 2 -> upsert to Qdrant + PostgreSQL
- [x] `GET /api/v1/documents/{document_id}/events` returns `200 OK` with an SSE stream of ingestion lifecycle events, including stages and percentage updates; missing Documents return `404`
- [x] `GET /api/v1/documents` returns `200 OK` and lists all Documents with filename, status (processing/ready/failed), page count, created date, and pagination metadata
- [x] `GET /api/v1/documents/{document_id}` returns `200 OK` with one Document and its current ingestion status and metadata; missing Documents return `404`
- [x] `DELETE /api/v1/documents/{document_id}` tombstones the Source, immediately removes every Version from Qdrant retrieval eligibility, retains audit data/assets for the configured retention period, and returns `204 No Content`; missing Documents return `404`
- [x] React UI has: upload button with drag-and-drop, document list with status badges, progress indicator during ingestion, and delete button
- [x] Image Anchors are extracted from PDFs, captioned, stored, and linked to the nearest text Evidence

## Blocked by

- #01-project-scaffold

## Comments

- 2026-07-13: Completed the guided Documents UI, version-aware ingestion lifecycle, Docling parsing, deterministic structural Context Headers, image extraction/captioning, Google Gemini embeddings, Qdrant eligibility promotion, retries, progress reporting, and Source deletion flow.
