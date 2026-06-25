# EvidentRAG — Adaptive RAG Engine with Evidence Retrieval Memory

**Status: ready-for-agent**

## Problem Statement

Users who query large document collections face three unsolved problems in current RAG systems: (1) every Query follows the same retrieval path regardless of complexity — a "compare X and Y" question gets the same treatment as "what is X?", (2) retrieval quality never improves over time because the system has no memory of which Evidence worked for which kinds of Queries, and (3) users cannot verify *why* an Answer says what it says because there's no sentence-level trace back to source Evidence.

## Solution

EvidentRAG is a Docker-Compose-runnable demo that showcases three novel capabilities:

- **ARAG Router**: an LLM classifier that selects one of four retrieval Routes (Simple, Multi-hop, Comparison, Aggregation) for each Query, then optionally decomposes multi-step Queries into sub-queries.
- **Evidence Retrieval Memory (ERM)**: a post-retrieval boost/penalty layer that learns from past retrieval outcomes — Evidence that successfully grounded Answers gets boosted for similar future Queries; irrelevant Evidence gets suppressed.
- **Sentence Traces**: every Answer is generated as structured JSON with inline citations linking each sentence to its supporting Evidence, rendered as an interactive evidence panel in the UI.

The stack is FastAPI + PostgreSQL + Qdrant + Redis, with a React/Vite/Tailwind/shadcn frontend, all orchestrated via Docker Compose. Embeddings use Google Gemini Embedding 2 (multimodal, 768-dim). Reranking uses Cohere Rerank API.

## User Stories

### Document Ingestion

1. As a user, I want to upload a PDF Document so that it becomes part of my Knowledge Base and can be queried.
2. As a user, I want to see upload progress (parsing → chunking → embedding — percentage) so that I know when a Document is ready to query.
3. As a user, I want to view a list of all ingested Documents with status (processing, ready, failed) so that I can manage my Knowledge Base.
4. As a user, I want to delete a Document and all its associated Evidence from both Qdrant and PostgreSQL so that I can remove stale content.
5. As a user, I want Documents with images to have those images extracted, captioned, and retrievable alongside text Evidence so that visual content is not lost.
6. As a user, I want text chunks to have Context Headers that describe where in the Document they came from so that the LLM has better context during Answer generation.

### Querying

7. As a user, I want to type a natural-language Query and receive an Answer so that I can explore my Knowledge Base.
8. As a user, I want to see which Route the ARAG Router selected for my Query (e.g., "Multi-hop") so that I understand how the system approached my question.
9. As a user, I want the Answer to stream token-by-token as it is generated so that I don't wait for the full response before reading.
10. As a user, I want to ask a factual "what is X" Query and get a single-pass retrieval response (Simple Route) so that straightforward questions are answered quickly.
11. As a user, I want to ask a multi-step Query like "what causes X, and how does that lead to Y" and have the system iteratively retrieve each step (Multi-hop Route) so that complex reasoning chains are answered correctly.
12. As a user, I want to ask a comparison Query like "compare X and Y" and have the system retrieve for both entities and synthesize differences (Comparison Route) so that I get a structured comparison.
13. As a user, I want to ask a broad overview Query like "tell me about the main themes in this document" and have the system aggregate across many Evidence chunks (Aggregation Route) so that I get a comprehensive summary.

### Evidence Traces

14. As a user, I want to see exactly which Evidence chunk supports each sentence in the Answer so that I can verify the system's claims.
15. As a user, I want to click on an Evidence ID and see the full source passage + its Context Header so that I can read the original context.
16. As a user, I want to click on an Evidence ID for an Image Anchor and see the image + caption so that I can inspect visual evidence.
17. As a user, I want to see the Document name and page number for each Evidence chunk so that I know where to find the original source.

### Evidence Retrieval Memory

18. As a user, I want to rate each Answer sentence as helpful or not (thumbs up/down) so that my feedback improves future retrievals.
19. As a user, I want future similar Queries to return more relevant Evidence because the system learned from my past ratings (ERM boost) so that retrieval quality improves over time.
20. As a user, I want Evidence I previously marked as irrelevant to be deprioritized for similar Queries (ERM penalty) so that bad results don't keep appearing.

### Evaluation

21. As a user, I want to define a Golden Dataset of (Query, expected Answer) pairs so that I can benchmark retrieval quality.
22. As a user, I want to run RAGAS evaluation (answer relevancy, faithfulness, context precision, context recall) against my Golden Dataset and see scores so that I have reproducible quality metrics.
23. As a user, I want to view evaluation scores in a dashboard with per-Query breakdowns so that I can identify where the system underperforms.
24. As a user, I want to add, edit, and remove Golden Dataset entries through the UI so that I can curate the benchmark.

### System Setup

25. As a user, I want to start the entire system with a single `docker compose up` command so that setup is trivial.
26. As a user, I want to provide my Google AI and Cohere API keys as environment variables in a `.env` file so that I don't hardcode secrets.

## Implementation Decisions

### Architecture

- The system is a single Docker Compose stack: FastAPI backend, React/Vite frontend (served via nginx or Vite dev server), PostgreSQL, Qdrant, Redis.
- Two Python modules form the core: the **Ingestion Pipeline** (async, multi-stage, progress-tracked) and the **Retrieval Pipeline** (query → classify → retrieve → rerank → ERM → generate).
- External API calls (Gemini Embedding, Cohere Rerank, Gemini LLM) are abstracted behind dependency-injectable service interfaces so tests can mock them.
- The ARAG Router is an LLM call (Gemini 2.5 Flash) that returns a Route enum and optional decomposed sub-queries.

### Data Model

PostgreSQL stores:

- **documents**: id, filename, status (processing/ready/failed), page_count, created_at
- **evidence**: id, document_id, chunk_index, content (text), context_header, embedding_id (Qdrant point ID), is_image_anchor
- **evidence_chunks**: (deprecated by evidence table above — single table for all Evidence)
- **queries**: id, query_text, selected_route, created_at
- **answers**: id, query_id, full_text, created_at
- **sentence_traces**: id, answer_id, sentence_index, sentence_text
- **sentence_trace_evidence**: trace_id, evidence_id
- **retrieval_failures**: id, query_id, evidence_id, created_at
- **erm_scores**: evidence_id, query_embedding_hash, boost_score, penalty_score, updated_at
- **golden_dataset**: id, query_text, expected_answer
- **eval_runs**: id, golden_dataset_id, ragas_scores (JSON), created_at

Qdrant stores:

- **evidentrag_evidence** collection: vectors (768-dim, Gemini Embedding 2), payload: {evidence_id, document_id, context_header, content, is_image_anchor}

### Retrieval Pipeline Contract

The SSE stream emits typed events:

```
route_selected: {route: "simple"|"multi_hop"|"comparison"|"aggregation", sub_queries: [...]}
retrieving: {stage: "dense"|"bm25"|"rrf"|"rerank"|"erm", candidates_count: int}
generating: {token: "..."}   // repeated per token
done: {answer: [{sentence: str, evidence_ids: [int]}], evidence: [{id, content, context_header, document_name, page}]}
```

### Frontend

- React/Vite with Tailwind CSS + shadcn/ui components.
- Three primary views: **Query** (chat-like interface with streaming), **Documents** (upload + list with status), **Evaluation** (Golden Dataset management + RAGAS dashboard).
- The Query view shows the selected Route badge, the streaming Answer with inline citation highlights, and a side panel with Evidence details.

### API Endpoints

- `POST /api/documents` — upload Document (multipart/form-data), returns document_id
- `GET /api/documents` — list all Documents with status
- `GET /api/documents/{id}/progress` — SSE stream of Ingestion Pipeline progress
- `DELETE /api/documents/{id}` — delete Document and all Evidence
- `POST /api/query` — submit Query, returns SSE stream
- `GET /api/query/history` — list past Queries and Answers
- `POST /api/eval/run` — run RAGAS evaluation against Golden Dataset
- `GET /api/eval/results` — list eval run results
- `GET /api/eval/golden-dataset` — list Golden Dataset entries
- `POST /api/eval/golden-dataset` — add entry
- `DELETE /api/eval/golden-dataset/{id}` — remove entry
- `POST /api/feedback` — submit User Rating (thumbs up/down for a sentence trace)

### ADRs in Effect

- **0001**: ARAG Router is a 4-route LLM classifier — no heuristic fallback.
- **0002**: ERM is a post-retrieval boost/penalty layer via cosine-similarity lookup — not a latent model.
- **0003**: Inline structured citations (JSON `[{sentence, evidence_ids}]`) — no post-hoc NLI attribution.
- **0004**: Cloud APIs for embeddings (Gemini Embedding 2) and reranking (Cohere) — no local model fallback.

## Testing Decisions

### Primary Seam

The **FastAPI endpoints** are the highest and only seam needed. Tests use `httpx.AsyncClient` (or `TestClient`) against the FastAPI app with dependency overrides that replace Qdrant, PostgreSQL, Gemini, and Cohere with mocks. Every test exercises external behavior only: HTTP request in, HTTP response (or SSE events) out.

### What Makes a Good Test

- Tests assert on the shape and content of HTTP responses, not on internal function calls.
- Mocked external services return realistic fixtures (e.g., Gemini returns plausible embeddings, Cohere returns plausible rerank scores, Qdrant returns plausible search results).
- SSE streams are collected as a list of typed events and asserted per event type.
- Ingestion tests use a real PDF fixture file and verify that PostgreSQL records are created correctly.

### Modules Tested

- Document upload, status tracking, and deletion endpoints.
- Query submission with SSE streaming — verifying events fire in order and the `done` event contains structured Answer + Sentence Traces.
- Golden Dataset CRUD and eval run endpoint.
- User Rating submission and ERM score changes.

### No Prior Art

This is a greenfield project with no existing tests. The test structure follows standard FastAPI testing conventions with `pytest` and `pytest-asyncio`.

## Out of Scope

- Multi-user authentication and authorization.
- Multi-tenancy (all Documents belong to a single implicit user).
- GraphRAG or knowledge graph construction.
- Multi-agent retrieval orchestration beyond the ARAG Router.
- Video or audio ingestion pipeline.
- Local embedding or reranking model fallback (per ADR-0004).
- Production deployment (no Kubernetes, no load balancing, no monitoring beyond Docker logs).
- CI/CD pipeline.
- PDF OCR — assumes PDFs have extractable text.
- Query history search or filtering.
- Export of Golden Dataset or eval results.

## Further Notes

- The primary demo dataset should be pre-seeded — a set of well-chosen PDFs (e.g., a mix of research papers, technical reports, and articles) that exercise all four ARAG Routes. This avoids the "cold start" where a user uploads nothing and has nothing to query.
- The `pyproject.toml` should be renamed from "rag" to "evidentrag" to match the project name.
- All API keys are passed via `.env` and referenced in `docker-compose.yml`. A `.env.example` file should be committed with placeholder values.
