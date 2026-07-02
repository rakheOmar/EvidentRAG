Status: ready-for-agent

## What to build

The full async Document Ingestion Pipeline: a user uploads a PDF through the UI, the backend parses it, chunks text, generates Contextual Chunk Headers (CCH), captions images, embeds everything via Gemini Embedding 2, upserts vectors to Qdrant, stores metadata in PostgreSQL, and streams progress back to the UI. The user can view a list of all uploaded Documents with their processing status and delete Documents (which cascades to Evidence, Qdrant vectors, and PostgreSQL rows).

## Acceptance criteria

- [ ] `POST /api/v1/documents` accepts multipart PDF upload, creates a Document resource, and returns `201 Created` with a `document_id`; invalid uploads return `400`, unsupported media returns `415`, and validation failures return `422`
- [ ] Upload triggers async ingestion: parse PDF (PyMuPDF) → chunk text at paragraph boundaries → generate CCH context headers via Utility LLM (Gemini 2.5 Flash) → caption images via Utility LLM → embed via Gemini Embedding 2 → upsert to Qdrant + PostgreSQL
- [ ] `GET /api/v1/documents/{document_id}/events` returns `200 OK` with an SSE stream of ingestion lifecycle events, including stages and percentage updates; missing Documents return `404`
- [ ] `GET /api/v1/documents` returns `200 OK` and lists all Documents with filename, status (processing/ready/failed), page count, created date, and pagination metadata
- [ ] `GET /api/v1/documents/{document_id}` returns `200 OK` with one Document and its current ingestion status and metadata; missing Documents return `404`
- [ ] `DELETE /api/v1/documents/{document_id}` removes the Document resource, all Evidence rows, and Qdrant vectors, and returns `204 No Content`; missing Documents return `404`
- [ ] React UI has: upload button with drag-and-drop, document list with status badges, progress bar during ingestion, delete button
- [ ] Image Anchors are extracted from PDFs, captioned, and stored alongside nearest text chunk

## Blocked by

- #01-project-scaffold
