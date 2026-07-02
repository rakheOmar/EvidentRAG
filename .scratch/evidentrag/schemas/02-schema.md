# EvidentRAG Schema

## Purpose

This schema supports the pre-seeded dataset for EvidentRAG.

- PostgreSQL stores structured metadata for Documents and Evidence.
- Qdrant stores vector embeddings for Evidence chunks.

## PostgreSQL

### documents

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `uuid` | primary key | Stable internal document ID |
| `title` | `text` | not null | Human-readable document title |
| `slug` | `text` | not null, unique | Stable readable identifier |
| `source_path` | `text` | not null, unique | Original seeded file path |
| `source_type` | `text` | not null, default `'pdf'` | Document type |
| `content_hash` | `text` | not null | Detect reseeds / dedupe |
| `page_count` | `integer` | not null | Number of pages |
| `metadata` | `jsonb` | not null, default `'{}'::jsonb` | Extra document metadata |
| `created_at` | `timestamptz` | not null, default `now()` | Audit timestamp |
| `updated_at` | `timestamptz` | not null, default `now()` | Audit timestamp |

### evidence

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `uuid` | primary key | Stable internal evidence ID |
| `document_id` | `uuid` | not null, references `documents(id)` on delete cascade | Link back to document |
| `locator` | `text` | not null, unique | Human-readable chunk handle like `bert-p3-c4` |
| `content` | `text` | not null | Actual chunk text |
| `content_hash` | `text` | not null | Detect duplicate chunk content |
| `context_header` | `text` | not null | Short prefix like `Passage from {title}, page {page}.` |
| `page` | `integer` | not null | Citation page |
| `chunk_index` | `integer` | not null | Chunk order within document |
| `token_count` | `integer` | not null | Useful for retrieval and generation tuning |
| `metadata` | `jsonb` | not null, default `'{}'::jsonb` | Extra chunk metadata |
| `created_at` | `timestamptz` | not null, default `now()` | Audit timestamp |
| `updated_at` | `timestamptz` | not null, default `now()` | Audit timestamp |

## Recommended PostgreSQL Indexes and Constraints

| Object | Rule | Why |
|---|---|---|
| `documents.slug` | unique | Prevent duplicate logical documents |
| `documents.source_path` | unique | Prevent reseeding the same file path |
| `evidence.locator` | unique | Stable readable chunk identity |
| `evidence(document_id, chunk_index)` | unique | Prevent duplicate chunk positions within one document |
| `evidence.document_id` | index | Fast lookup of a document's evidence |

## Qdrant

### Collection: `evidentrag_evidence`

| Field | Value |
|---|---|
| Collection name | `evidentrag_evidence` |
| Vector size | `768` |
| Distance | `cosine` |

### Payload

| Key | Value |
|---|---|
| `evidence_id` | UUID from PostgreSQL `evidence.id` |
| `document_id` | UUID from PostgreSQL `documents.id` |
| `document_title` | Document title |
| `document_slug` | Document slug |
| `locator` | Human-readable chunk handle |
| `page` | Source page |
| `chunk_index` | Chunk order |

Optional payload:
- `context_header`

## Data Flow

| Step | Result |
|---|---|
| Document loaded | insert/update `documents` |
| Document chunked | generate Evidence records |
| Evidence stored | insert/update `evidence` |
| Evidence embedded | create 768-dim vectors |
| Vectors upserted | store in `evidentrag_evidence` |

## Context Header

For the seeded dataset, `context_header` should be deterministic:

```text
Passage from {document_title}, page {page}.
```

This keeps Evidence chunks self-contained for retrieval without requiring an LLM-generated header.

## Summary

- `documents` stores source Document metadata.
- `evidence` stores chunk metadata and text.
- `evidentrag_evidence` stores vector embeddings for Evidence.
