# EvidentRAG Issue 4 Schema

## Purpose

This schema extends the pre-seeded EvidentRAG corpus with persistence, retrieval tracing, citation tracing, and streaming support needed for the simple route query pipeline.

- PostgreSQL stores query, answer, citation, and retrieval trace records.
- Qdrant stores Evidence vectors and supports hybrid dense + sparse retrieval.
- Redis Pub/Sub carries transient query progress events for SSE delivery.

## PostgreSQL

### Existing tables

Issue 4 builds on the existing corpus tables documented in `02-schema.md`:

- `documents`
- `evidence`

Those tables remain the source of truth for retrieved Evidence metadata and chunk content.

---

## queries

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `uuid` | primary key | Stable internal query ID |
| `query_text` | `text` | not null | Original user-submitted question |
| `selected_route` | `text` | not null, default `'simple'` | Router output, hardcoded to `simple` for Issue 4 |
| `status` | `text` | not null, default `'pending'` | Pipeline state: `pending`, `running`, `completed`, `failed` |
| `metadata` | `jsonb` | not null, default `'{}'::jsonb` | Flexible query/run metadata |
| `error_message` | `text` | nullable | Failure reason if the query fails |
| `created_at` | `timestamptz` | not null, default `now()` | Creation timestamp |
| `updated_at` | `timestamptz` | not null, default `now()` | Last status/update timestamp |
| `completed_at` | `timestamptz` | nullable | Timestamp when query finished |

### Status values

Allowed `status` values:

```text
pending
running
completed
failed
```

---

## answers

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `uuid` | primary key | Stable internal answer ID |
| `query_id` | `uuid` | not null, unique, references `queries(id)` on delete cascade | One-to-one link from Query to Answer |
| `full_text` | `text` | not null | Flattened answer text assembled from structured sentence output |
| `model_name` | `text` | nullable | Model used to generate the answer |
| `prompt_version` | `text` | nullable | Prompt/template version used for generation |
| `metadata` | `jsonb` | not null, default `'{}'::jsonb` | Token usage, latency, raw generation metadata, etc. |
| `created_at` | `timestamptz` | not null, default `now()` | Audit timestamp |

---

## sentence_traces

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `id` | `uuid` | primary key | Stable internal sentence trace ID |
| `answer_id` | `uuid` | not null, references `answers(id)` on delete cascade | Link back to the generated answer |
| `sentence_index` | `integer` | not null | Sentence order within the answer |
| `sentence_text` | `text` | not null | One generated sentence from the structured JSON output |

---

## sentence_trace_evidence

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `trace_id` | `uuid` | not null, references `sentence_traces(id)` on delete cascade | Sentence being supported |
| `evidence_id` | `uuid` | not null, references `evidence(id)` on delete cascade | Evidence cited by the sentence |
| `citation_index` | `integer` | not null | Citation order within the sentence |

Composite primary key:

- (`trace_id`, `evidence_id`)

Additional unique constraint:

- (`trace_id`, `citation_index`)

---

## query_evidence_candidates

| Column | Type | Constraints | Purpose |
|---|---|---|---|
| `query_id` | `uuid` | not null, references `queries(id)` on delete cascade | Query that produced this retrieval candidate |
| `evidence_id` | `uuid` | not null, references `evidence(id)` on delete cascade | Retrieved Evidence candidate |
| `stage` | `text` | not null | Retrieval stage: `dense`, `sparse`, `fused`, `reranked`, `selected` |
| `rank` | `integer` | not null | Rank within the retrieval stage |
| `score` | `double precision` | nullable | Retrieval, fusion, or reranking score if available |
| `metadata` | `jsonb` | not null, default `'{}'::jsonb` | Extra retrieval/debug metadata |
| `created_at` | `timestamptz` | not null, default `now()` | Audit timestamp |

Composite primary key:

- (`query_id`, `stage`, `evidence_id`)

Additional unique constraint:

- (`query_id`, `stage`, `rank`)

### Stage values

Allowed `stage` values:

```text
dense
sparse
fused
reranked
selected
```

---

## Recommended PostgreSQL Indexes and Constraints

| Object | Rule | Why |
|---|---|---|
| `queries.status` | index | Fast filtering of pending/running/completed/failed queries |
| `queries.created_at` | index | Fast recent-query history listing |
| `queries.selected_route` | index | Future route-based filtering |
| `answers.query_id` | unique | Enforce one Answer per Query |
| `sentence_traces(answer_id, sentence_index)` | unique | Prevent duplicate sentence positions within one answer |
| `sentence_traces.answer_id` | index | Fast lookup of all traces for an answer |
| `sentence_trace_evidence.evidence_id` | index | Fast reverse lookup of where evidence was cited |
| `sentence_trace_evidence(trace_id, citation_index)` | unique | Preserve citation order per sentence |
| `query_evidence_candidates(query_id, stage, rank)` | unique | Prevent duplicate ranks inside the same retrieval stage |
| `query_evidence_candidates.evidence_id` | index | Fast reverse lookup of retrieval usage |
| `query_evidence_candidates(query_id)` | index | Fast lookup of full retrieval trace for one query |

---

## Relationships

| From | To | Cardinality | Notes |
|---|---|---|---|
| `queries` | `answers` | one-to-one | A Query produces at most one persisted Answer |
| `answers` | `sentence_traces` | one-to-many | An Answer contains ordered generated sentences |
| `sentence_traces` | `evidence` | many-to-many | Each sentence cites one or more Evidence rows via `sentence_trace_evidence` |
| `queries` | `evidence` | many-to-many | Each query retrieves many Evidence candidates via `query_evidence_candidates` |
| `documents` | `evidence` | one-to-many | A Document is split into many Evidence chunks |

## Qdrant

### Collection: `evidentrag_evidence`

Issue 4 keeps the existing collection name and extends it to support hybrid retrieval.

| Field | Value |
|---|---|
| Collection name | `evidentrag_evidence` |
| Dense vector name | `dense` |
| Dense vector size | `768` |
| Dense distance | `cosine` |
| Sparse vector name | `sparse` |
| Sparse modifier | `idf` |

### Retrieval pattern

Hybrid retrieval uses:

- dense semantic search over named vector `dense`
- sparse lexical/BM25-style search over named vector `sparse`
- server-side fusion with reciprocal rank fusion, RRF

Target retrieval sizes for Issue 4:

| Stage | Target size |
|---|---:|
| Dense candidates | 20 |
| Sparse candidates | 20 |
| Fused candidates | 20 |
| Reranked candidates sent to LLM | 5 |

### Payload

The payload remains compatible with the existing seeded corpus schema.

| Key | Value |
|---|---|
| `evidence_id` | UUID from PostgreSQL `evidence.id` |
| `document_id` | UUID from PostgreSQL `documents.id` |
| `document_title` | Document title |
| `document_slug` | Document slug |
| `locator` | Human-readable chunk handle |
| `page` | Source page |
| `chunk_index` | Chunk order |
| `context_header` | Short citation preface |

### Qdrant role

Qdrant is not the durable source of truth.

It is the retrieval index for Evidence chunks. PostgreSQL remains the source of truth for Evidence text, document metadata, query records, answer records, and citation traces.

## Redis

### Pub/Sub channel

Each query publishes pipeline events to a dedicated channel:

```text
query:{query_id}:events
```

### Event types

| Event | Purpose |
|---|---|
| `route_selected` | Emits the chosen route |
| `retrieving` | Emits retrieval progress or retrieved-candidate milestones |
| `generating` | Emits streamed sentence or token progress |
| `done` | Emits the final structured answer payload |
| `error` | Emits terminal pipeline failure information |

Redis is transient transport only for Issue 4.

The durable system of record remains PostgreSQL.

## Data Flow

| Step | Result |
|---|---|
| Query submitted | Insert `queries` row with `selected_route = 'simple'` and `status = 'pending'` |
| Query starts | Update `queries.status` to `running` |
| Route selected | Emit `route_selected` event through Redis |
| Hybrid retrieval | Fetch dense and sparse Evidence candidates from Qdrant |
| Candidate trace persisted | Insert dense, sparse, and fused candidates into `query_evidence_candidates` |
| Rerank | Choose top Evidence rows for generation |
| Selected context persisted | Insert reranked/selected candidates into `query_evidence_candidates` |
| LLM generation | Stream structured sentence output via Redis/SSE |
| Answer persisted | Insert `answers`, `sentence_traces`, and `sentence_trace_evidence` |
| Query completed | Update `queries.status = 'completed'`, set `completed_at`, and emit `done` |
| Query fails | Update `queries.status = 'failed'`, set `error_message`, and emit `error` |

## Structured Answer Shape

Issue 4 expects the generated answer to resolve to a JSON array shaped like:

```json
[
  {
    "sentence": "The answer sentence.",
    "evidence_ids": ["uuid-1", "uuid-2"]
  }
]
```

Notes:

- `evidence_ids` are UUID strings, not integers.
- `full_text` in `answers` is the ordered concatenation of all `sentence` values.
- `sentence_index` is derived from array order.
- `citation_index` is derived from the order of `evidence_ids` within each sentence object.

## Summary

- `documents` and `evidence` remain the retrieval corpus schema.
- `queries`, `answers`, `sentence_traces`, and `sentence_trace_evidence` persist query execution and sentence-level citation traces.
- `query_evidence_candidates` persists retrieval, fusion, rerank, and selected-context traces.
- `evidentrag_evidence` supports named dense and sparse vectors for hybrid retrieval.
- Redis Pub/Sub supports live SSE updates but is not a durable store.
