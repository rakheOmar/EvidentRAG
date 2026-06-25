Status: ready-for-agent

## What to build

The core query pipeline for the Simple Route. A user types a Query into the UI. The ARAG Router (Gemini 2.5 Flash) classifies it — initially routing all queries to Simple. The backend runs hybrid retrieval (dense + BM25 in parallel against Qdrant), fuses results via RRF, reranks via Cohere Rerank API, and generates a structured Answer via Gemini 2.5 Pro with inline citations (`[{sentence, evidence_ids}]`). The entire flow streams to the UI via SSE, showing the selected route, retrieval progress, and token-by-token generation. The Answer is displayed with basic text formatting and the route badge.

## Acceptance criteria

- [ ] `POST /api/query` accepts `{query_text}` and returns an SSE stream
- [ ] SSE events fire in order: `route_selected` → `retrieving` → `generating` (per token) → `done`
- [ ] `route_selected` event contains `{route: "simple", sub_queries: []}`
- [ ] ARAG Router (Gemini 2.5 Flash) classifies the Query — initially only Simple Route is implemented
- [ ] Hybrid retrieval: dense vector search (Gemini Embedding 2) and BM25 keyword search run concurrently against Qdrant
- [ ] RRF fuses dense + BM25 results inside Qdrant
- [ ] Cohere Rerank API reranks the fused candidates
- [ ] Gemini 2.5 Pro generates an Answer as structured JSON `[{sentence: str, evidence_ids: [int]}]`
- [ ] `done` event contains the full Answer with Sentence Traces and Evidence payload
- [ ] React UI: chat-like input, streaming token display, route badge (showing "Simple")
- [ ] Answer and Sentence Traces are persisted in PostgreSQL (`queries`, `answers`, `sentence_traces`, `sentence_trace_evidence` tables)
- [ ] Gemini, Cohere, and Qdrant calls are dependency-injected so tests can mock them

## Blocked by

- #01-project-scaffold
- #02-pre-seeded-dataset
