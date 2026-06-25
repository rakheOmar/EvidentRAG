Status: ready-for-agent

## What to build

The full async Document Ingestion Pipeline: a user uploads a PDF through the UI, the backend parses it, chunks text, generates Contextual Chunk Headers (CCH), captions images, embeds everything via Gemini Embedding 2, upserts vectors to Qdrant, stores metadata in PostgreSQL, and streams progress back to the UI. The user can view a list of all uploaded Documents with their processing status and delete Documents (which cascades to Evidence, Qdrant vectors, and PostgreSQL rows).

## Acceptance criteria

- [ ] `POST /api/documents` accepts multipart PDF upload and returns a `document_id`
- [ ] Upload triggers async ingestion: parse PDF (PyMuPDF) → chunk text at paragraph boundaries → generate CCH context headers via Utility LLM (Gemini 2.5 Flash) → caption images via Utility LLM → embed via Gemini Embedding 2 → upsert to Qdrant + PostgreSQL
- [ ] `GET /api/documents/{id}/progress` returns SSE stream of ingestion stages with percentage
- [ ] `GET /api/documents` lists all Documents with filename, status (processing/ready/failed), page count, created date
- [ ] `DELETE /api/documents/{id}` removes Document, all Evidence rows, and Qdrant vectors
- [ ] React UI has: upload button with drag-and-drop, document list with status badges, progress bar during ingestion, delete button
- [ ] Image Anchors are extracted from PDFs, captioned, and stored alongside nearest text chunk

## Blocked by

- #01-project-scaffold
