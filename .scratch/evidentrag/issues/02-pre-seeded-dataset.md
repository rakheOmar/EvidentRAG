Status: ready-for-agent

## What to build

A seed script (or FastAPI startup hook) that populates the database with a curated set of demo Documents and Evidence. The script embeds text passages via Gemini Embedding 2 and upserts them directly into Qdrant, while storing Document + Evidence metadata in PostgreSQL. This seed data exercises all four ARAG Routes: Simple (factual lookup), Multi-hop (chained reasoning), Comparison (entity differences), and Aggregation (broad summary). The seed data enables downstream slices to be tested without waiting for the Document Ingestion Pipeline.

## Acceptance criteria

- [ ] PostgreSQL `documents` and `evidence` tables are created via migration/startup script
- [ ] Qdrant `evidentrag_evidence` collection exists with correct vector dimension (768)
- [ ] At least 3 Documents are seeded with varied content that exercises Simple, Multi-hop, Comparison, and Aggregation query types
- [ ] Evidence chunks are embedded via Gemini Embedding 2 and stored in Qdrant
- [ ] Evidence metadata (content, context header, document reference, page) is stored in PostgreSQL
- [ ] Running `docker compose up` on a fresh system populates seed data automatically

## Blocked by

- #01-project-scaffold
