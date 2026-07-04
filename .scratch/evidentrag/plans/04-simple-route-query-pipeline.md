# Issue 4: Simple Route Query Pipeline

## Summary

Build the core query pipeline: user submits a Query → ARAG Router classifies it (hardcoded to Simple) → hybrid retrieval (dense + BM25 via Qdrant server-side) → RRF fusion → Cohere rerank → Gemini 2.5 Pro generates structured JSON answer with inline citations → streamed to client via SSE. Results persisted in PostgreSQL. React chat UI displays streaming answers with route badge and clickable citation markers.

## Current Status

### Done

- Database schema foundation is implemented in `server/app/infrastructure/db/models.py`:
  - `Query`
  - `Answer`
  - `SentenceTrace`
  - `SentenceTraceEvidence`
  - `QueryEvidenceCandidate`
- DB constraints for `queries.status` and `query_evidence_candidates.stage` are implemented.
- Qdrant collection schema is updated for named vectors:
  - dense vector `dense`
  - sparse vector `sparse`
- `QdrantStore.hybrid_search(...)` is implemented.
- Demo seeding writes named dense vectors in Qdrant.
- `CohereSettings` is implemented in config.
- `RerankClient` is implemented in `server/app/infrastructure/reranker/reranker.py`.
- `session_factory`, `embedding_client`, `llm_client`, and `rerank_client` are attached to `app.state` during app startup.
- `QueryPipeline` is implemented in `server/app/application/query_pipeline/query_pipeline.py`.
- `JsonStreamParser` is implemented in `server/app/application/query_pipeline/json_stream_parser.py`.
- `QueryPipeline` currently covers:
  - lifecycle (`pending` -> `running` -> `completed`)
  - failure path (`failed`, `error_message`, `error` event)
  - retrieval trace staging (`dense`, `sparse`, `fused`)
  - rerank/selected staging (`reranked`, `selected`)
  - sentence-based `generating` events
  - final `Answer` / `SentenceTrace` / `SentenceTraceEvidence` persistence
- Worker orchestration is implemented in `server/app/worker.py`:
  - worker startup builds runtime dependencies
  - worker shutdown closes Redis and disposes the engine
  - `run_query_pipeline(ctx, query_id)` delegates into `QueryPipeline`
- Queries API surface is substantially implemented:
  - `POST /api/v1/queries`
  - `GET /api/v1/queries`
  - `GET /api/v1/queries/{query_id}`
  - `GET /api/v1/queries/{query_id}/answer`
  - `GET /api/v1/queries/{query_id}/events`
- `POST /api/v1/queries` now enqueues `run_query_pipeline` when `app.state.job_queue` is configured.
- Query API schemas are substantially implemented in `server/app/api/schemas/queries.py`.
- SSE helpers are implemented in `server/app/api/sse/sse.py`.
- Full server test suite is green at this stage.
- Vite dev proxy configuration for `/api` and `/events` (with WebSocket support) added to `client/vite.config.ts`.
- `app.frontend()` integration in `server/app/frontend.py` with environment-gated production mode.
- Root `Dockerfile` with multi-stage build (client builder + server base + production/dev targets).
- `server/Dockerfile` kept as Python-only for the worker service.
- `docker-compose.yml` updated: backend builds from root `Dockerfile` with `target: production`; frontend service gated behind `profiles: [dev]`.
- Dev scripts added: `scripts/dev-frontend.ps1`, `scripts/dev-all.ps1`.
- Pre-commit checks documented in `AGENTS.md`.

### Not Done Yet

- end-to-end ARQ runtime validation against a live worker process
- frontend chat UI and SSE client flow (`app.tsx`, `api.ts`, `use-query.ts`, `chat.tsx`, `evidence-panel.tsx`)

## Decisions from Grilling Session

| Decision | Choice | Rationale |
|---|---|---|
| BM25 sparse vectors | Qdrant server-side native BM25 | No Python-side sparse computation, IDF stays consistent as corpus grows |
| ARAG Router | Hardcoded `simple` return | Only one route implemented; LLM classifier deferred to Issue 6 |
| Streaming strategy | Custom incremental JSON parser with sentence-based SSE | Cleaner client contract than token fragments while still feeling live |
| Citation format | `[{sentence: str, evidence_ids: [str]}]` with UUIDs | PRD says `int` but our Evidence IDs are UUIDs |
| Pipeline coordination | Redis Pub/Sub via ARQ task queue | Survives client disconnects, decouples API from pipeline |
| Task queue | ARQ (async-native, Redis-backed) | Lightweight, fits async codebase, uses existing Redis |
| DB schema scope | Include retrieval traces via `QueryEvidenceCandidate` | Retrieval behavior should be inspectable from day one |
| Dependency injection | `app.state` pattern | Consistent with existing codebase |
| Frontend scope | Functional chat UI with citations | Polish deferred to Issue 9 |
| Hybrid search | `query_points` + `prefetch` + `FusionQuery(Fusion.RRF)` | Top-20 per sub-query → top-20 fused → Cohere top-5 → LLM |
| Query lifecycle | Create with route=`simple`, status=`pending`; worker drives `running/completed/failed` | Keeps POST semantics simple and preserves status transitions |
| Failure semantics | No partial `Answer`; retrieval traces are best-effort | Failed generations should not leave partial answer rows behind |
| SSE completion contract | `done` includes full final structured payload | Avoids an extra round trip while keeping `GET /answer` as durable read model |
| Validation strategy | Enforce `status` and retrieval `stage` in app code and DB constraints | Prevents drift and bad state rows |

---

## Proposed Changes

### 1. Config & Dependencies

#### [MODIFY] [pyproject.toml](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/pyproject.toml)
- Add `arq` dependency for the task queue worker.
- Status: done.

#### [MODIFY] [config.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/core/config.py)
- Add `CohereSettings` dataclass: `api_key`, `model` (default `rerank-english-v3.0`).
- Add `cohere: CohereSettings` field to `Settings`, populated from `COHERE_API_KEY` and `COHERE_RERANK_MODEL` env vars.
- Status: done.

---

### 2. Database Models

#### [MODIFY] [models.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/infrastructure/db/models.py)
Add five new SQLAlchemy models:

- **`Query`** (`queries`): `id` (UUID PK), `query_text` (Text), `selected_route` (Text, default `"simple"`), `status` (Text, default `"pending"`), `metadata` (JSONB), `error_message` (Text, nullable), `created_at`, `updated_at`, `completed_at` (Timestamp, nullable).
- Add DB check constraint limiting `queries.status` to `pending|running|completed|failed`.
- **`Answer`** (`answers`): `id` (UUID PK), `query_id` (FK → queries), `full_text` (Text), `model_name` (Text, nullable), `prompt_version` (Text, nullable), `metadata` (JSONB), `created_at` (Timestamp).
- **`SentenceTrace`** (`sentence_traces`): `id` (UUID PK), `answer_id` (FK → answers), `sentence_index` (Integer), `sentence_text` (Text).
- **`SentenceTraceEvidence`** (`sentence_trace_evidence`): `trace_id` (FK → sentence_traces), `evidence_id` (FK → evidence), `citation_index` (Integer), composite PK on (`trace_id`, `evidence_id`), unique constraint on (`trace_id`, `citation_index`).
- **`QueryEvidenceCandidate`** (`query_evidence_candidates`): `query_id` (FK → queries), `evidence_id` (FK → evidence), `stage` (Text), `rank` (Integer), `score` (Double Precision, nullable), `metadata` (JSONB), `created_at` (Timestamp), composite PK on (`query_id`, `stage`, `evidence_id`), unique constraint on (`query_id`, `stage`, `rank`).
- Add DB check constraint limiting `query_evidence_candidates.stage` to `dense|sparse|fused|reranked|selected`.

Relationships: `Query` → `Answer` (one-to-one), `Answer` → `SentenceTrace` (one-to-many), `SentenceTrace` → `Evidence` (many-to-many via join table), `Query` → `Evidence` (many-to-many via retrieval-trace join table).

- Status: done.

---

### 3. Qdrant Named Vectors + BM25

#### [MODIFY] [client.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/infrastructure/qdrant/client.py)

Update `ensure_collection` and `reset_collection` to create the collection with:
- Named dense vector: `"dense"` → `VectorParams(size=768, distance=Distance.COSINE)`
- Named sparse vector: `"sparse"` → `SparseVectorParams(modifier=Modifier.IDF)`

Add a `hybrid_search` method:
- Accepts a dense query vector and sparse query text.
- Uses `query_points` with two `Prefetch` entries (dense search using `"dense"`, sparse search using `"sparse"`) and `FusionQuery(fusion=Fusion.RRF)`.
- Top-20 prefetch per sub-query, top-20 after fusion.
- Returns list of scored points with payloads.

- Status: done.
- Note: `hybrid_search(...)` now exposes the pipeline-friendly contract `query_text + dense_vector`, and the sparse leg is delegated to Qdrant using the named sparse query path (`using="sparse"`).

#### [MODIFY] [seed_demo_data.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/seed/seed_demo_data.py)

Update point construction to use named vector format:
```python
vector={"dense": dense_embedding_vector}
# Sparse vector text stored in payload — Qdrant generates BM25 vectors server-side
```

- Status: partially done. Named dense vector seeding is implemented, and runtime retrieval now uses the query-text sparse leg; remaining work here is full end-to-end runtime validation under the live worker flow.

---

### 4. Cohere Rerank Client

#### [NEW] [reranker.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/infrastructure/reranker/reranker.py)

`RerankClient` class:
- Constructor takes `CohereSettings` and an optional `httpx.AsyncClient`.
- `rerank(query: str, documents: list[str], top_n: int = 5) -> list[RerankResult]` — calls `POST https://api.cohere.com/v2/rerank` with Bearer auth.
- Returns list of `RerankResult(index: int, relevance_score: float)` sorted by score descending.

- Status: done.

---

### 5. Query Pipeline (Application Layer)

#### [NEW] [query_pipeline.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/application/query_pipeline/query_pipeline.py)

`QueryPipeline` class orchestrating the full flow:

1. **Route** — return `{"route": "simple", "sub_queries": []}` (hardcoded).
2. **Retrieve** — embed query text via `EmbeddingClient`, call `QdrantStore.hybrid_search`, publish `retrieving` events to Redis Pub/Sub, and best-effort persist dense/sparse/fused candidates to `QueryEvidenceCandidate`.
3. **Rerank** — pass top-20 fused candidates to `RerankClient.rerank(top_n=5)` and best-effort persist `reranked` plus `selected` candidates.
4. **Generate** — build a prompt with the top-5 evidence chunks, call `LLMClient.generate_stream`, parse the JSON stream incrementally to extract completed sentences, and publish `generating` events sentence-by-sentence.
5. **Persist** — parse the completed JSON, create `Answer`, `SentenceTrace`, and `SentenceTraceEvidence` rows in PostgreSQL, update `Query.status` to `completed`, set `completed_at`, and publish `done` with the full structured payload.
6. **Fail** — on terminal errors, update `Query.status` to `failed`, store `error_message`, publish `error`, and do not persist a partial `Answer`.

- Status: done.
- Note: the current implementation publishes `route_selected`, `retrieving`, `generating`, `done`, and `error`, stages retrieval/rerank candidates, persists the final answer graph, and now publishes the full structured answer payload in `done`.

#### [NEW] [json_stream_parser.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/application/query_pipeline/json_stream_parser.py)

Incremental JSON parser:
- Buffers raw tokens from the LLM stream.
- Detects when a `"sentence"` string value completes and yields the text.
- Does not expose raw token fragments to the client.
- After the stream ends, parses the full accumulated JSON to extract the complete `[{sentence, evidence_ids}]` structure.

- Status: done.

---

### 6. ARQ Worker

#### [NEW] [worker.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/worker.py)

ARQ worker settings module:
- Defines a `run_query_pipeline` async task function.
- Initialises shared resources on worker startup (DB engine, session factory, Qdrant client, LLM client, embedding client, rerank client, Redis).
- The task function receives a `query_id`, marks the query `running`, creates a `QueryPipeline`, runs it, and publishes SSE events to a Redis Pub/Sub channel `query:{query_id}:events`.

- Status: done for in-process worker orchestration.
- Still missing from this section:
  - end-to-end runtime validation with a live ARQ worker process

#### [MODIFY] [docker-compose.yml](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/docker-compose.yml)

Worker service using `server/Dockerfile` (Python-only). Backend service moved to root `Dockerfile` with multi-stage build. Frontend service gated behind `profiles: [dev]`.

- Status: done.

---

### 7. API Layer

#### [NEW] [queries.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/api/schemas/queries.py)

Pydantic request/response schemas:
- `QueryCreate`: `query_text: str`
- `QueryResponse`: `id`, `query_text`, `selected_route`, `status`, `error_message`, `created_at`, `updated_at`, `completed_at`
- `AnswerResponse`: `id`, `query_id`, `full_text`, `sentences: list[SentenceTraceResponse]`, `evidence: list[EvidenceResponse]`
- `SentenceTraceResponse`: `sentence_index`, `sentence_text`, `evidence_ids: list[str]`
- `EvidenceResponse`: `id`, `content`, `context_header`, `document_title`, `document_slug`, `page`
- `QueryEvidenceCandidateResponse` (optional/debug endpoint or future use): `query_id`, `evidence_id`, `stage`, `rank`, `score`

- Status: mostly done. Core request/response schemas are implemented; debug/retrieval-trace response models are still optional and not exposed.

#### [NEW] [queries.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/api/routes/queries.py)

Endpoints:
- `POST /api/v1/queries` — validate input, insert `Query` row (`selected_route="simple"`, `status="pending"`), enqueue ARQ job, return `201` with `QueryResponse`.
- `GET /api/v1/queries/{query_id}/events` — subscribe to Redis Pub/Sub channel `query:{query_id}:events`, yield SSE events (`text/event-stream`). Events: `route_selected`, `retrieving`, `generating`, `done`, `error`.
- `GET /api/v1/queries/{query_id}` — fetch Query row, return `QueryResponse` or `404`.
- `GET /api/v1/queries/{query_id}/answer` — fetch Answer + SentenceTraces + Evidence, return `AnswerResponse` if complete, `202` if pending, `404` if missing.
- `GET /api/v1/queries` — list past Queries with pagination.
- Retrieval trace endpoints are optional for Issue 4 API surface; traces are persisted even if not yet exposed directly.

- Status: partially done.
- Implemented now:
  - `POST /api/v1/queries`
  - `GET /api/v1/queries/{query_id}`
  - `GET /api/v1/queries`
  - `GET /api/v1/queries/{query_id}/answer`
  - `GET /api/v1/queries/{query_id}/events`
  - enqueue hook from `POST /api/v1/queries` when `app.state.job_queue` is configured
- Still missing from this section:
  - retrieval-trace endpoints, if we decide to expose them

#### [NEW] [sse.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/api/sse/sse.py)

SSE helper:
- `sse_event(event: str, data: dict) -> str` — formats a single SSE event string (`event: ...\ndata: ...\n\n`).
- `redis_pubsub_stream(redis, channel: str) -> AsyncIterator[str]` — subscribes to a Redis Pub/Sub channel and yields formatted SSE event strings until a `done` or `error` event is received.
- `done` should carry the full final answer payload so the client can complete without an immediate follow-up fetch.

- Status: done.

#### [MODIFY] [main.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/main.py)

- Import and include the queries router with prefix `/api/v1`.
- Instantiate `LLMClient`, `EmbeddingClient`, `RerankClient` during lifespan and attach to `app.state`.
- Create ARQ `ArqRedis` connection pool and attach to `app.state`.
- Create `session_factory` and attach to `app.state` (currently only used locally in lifespan).
- Call `mount_frontend(app, settings)` after routes are registered (production only).

- Status: partially done.
- Items implemented:
  - queries router included
  - `session_factory` attached to `app.state`
  - `EmbeddingClient` attached to `app.state`
  - `LLMClient` attached to `app.state`
  - `RerankClient` attached to `app.state`
  - `mount_frontend()` integration
- Still missing:
  - end-to-end runtime validation of the live ARQ job queue in app startup

#### [NEW] [frontend.py](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/server/app/frontend.py)

- `mount_frontend(app, settings)` — only mounts when `APP_ENV=production`, resolves the `client_dist_path`, and calls `app.frontend("/", directory=..., fallback="index.html")` for SPA client-side routing.

- Status: done.

#### [NEW] [Dockerfile](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/Dockerfile)

Multi-stage root Dockerfile:
- `client-builder` stage: builds the React app with `npm run build`.
- `server-base` stage: Python + uv sync (shared with dev target).
- `production` target: copies `client/dist` into the server image, sets `APP_ENV=production`.
- `dev` target: API-only, no client build.

- Status: done.

#### [MODIFY] [docker-compose.yml](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/docker-compose.yml)

- Backend builds from root `Dockerfile` with `target: production`.
- Worker builds from `server/Dockerfile` (Python-only).
- Frontend service gated behind `profiles: [dev]` (excluded from `docker compose up` by default).

- Status: done.

---

### 8. Frontend

#### [MODIFY] [vite.config.ts](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/vite.config.ts)
- Add `server.proxy` to forward `/api` and `/events` (WebSocket) requests to the backend at `http://localhost:8000` during local dev.
- Status: done.

#### [MODIFY] [app.tsx](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/src/app.tsx)
- Replace placeholder with the chat interface layout.

#### [NEW] [api.ts](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/src/lib/api.ts)
- `createQuery(queryText: string): Promise<QueryResponse>` — POST to `/api/v1/queries`.
- `subscribeToQueryEvents(queryId: string, handlers): void` — connects to `GET /api/v1/queries/{query_id}/events` via `EventSource`, dispatches to typed handler callbacks.
- `fetchAnswer(queryId: string): Promise<AnswerResponse>` — GET `/api/v1/queries/{query_id}/answer`.
- `fetchQueryHistory(): Promise<QueryResponse[]>` — GET `/api/v1/queries`.

#### [NEW] [use-query.ts](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/src/hooks/use-query.ts)
- React hook managing query lifecycle: submitting, SSE subscription, state transitions (idle → routing → retrieving → generating → done), accumulated sentences, final answer.

#### [NEW] [chat.tsx](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/src/components/chat.tsx)
- Chat interface: input box at bottom, message feed above.
- Each answer shows a route `Badge` ("Simple"), streamed sentence text, and clickable `[1]` citation markers.

#### [NEW] [evidence-panel.tsx](file:///c:/Users/rakhe/Desktop/Code/Projects/RAG/client/src/components/evidence-panel.tsx)
- Side panel / drawer showing Evidence detail when a citation marker is clicked: content, context header, document title, page number.

---

## Verification Plan

### Automated Tests

```bash
cd server && uv run pytest tests/test_queries.py -v
```

- Mock `EmbeddingClient`, `LLMClient`, `RerankClient`, `QdrantStore` via `app.state` overrides.
- `POST /api/v1/queries` → assert `201`, query persisted in DB with `selected_route="simple"` and status `"pending"`.
- Worker start / pipeline success → assert status transitions `pending` → `running` → `completed` and `completed_at` is populated.
- SSE stream → assert events fire in order: `route_selected` → `retrieving` → one or more sentence-based `generating` events → `done`.
- `done` event → assert payload contains `answer.sentences` with `evidence_ids` as UUID strings.
- `done` event → assert payload includes the full final structured answer so no extra fetch is required to render completion.
- `GET /api/v1/queries/{id}` → assert `200` with correct route metadata.
- `GET /api/v1/queries/{id}/answer` → assert `200` with structured answer after pipeline completes, `202` while pending.
- `GET /api/v1/queries` → assert `200` with list of queries.
- Retrieval trace persistence → assert all five stages (`dense`, `sparse`, `fused`, `reranked`, `selected`) are recorded when available.
- Retrieval trace persistence failure → assert query can still complete successfully if candidate trace writes fail.
- Generation failure → assert query becomes `failed`, `error_message` is set, no partial `Answer` row exists, and any already-persisted retrieval traces remain.

### Current Automated Coverage

- Implemented and green:
  - DB model tests for all new Issue 4 tables
  - Qdrant store tests for named vectors and hybrid search request shape
  - seed tests for named-vector Qdrant upserts
  - startup tests for `session_factory`, `embedding_client`, `llm_client`, and `rerank_client` wiring
  - integration tests for:
    - `POST /api/v1/queries`
    - `GET /api/v1/queries`
    - `GET /api/v1/queries/{id}`
    - `GET /api/v1/queries/{id}/answer` pending/completed/missing cases
  - route-unit test for enqueueing `run_query_pipeline` from `POST /api/v1/queries`
  - SSE helper unit tests
  - reranker unit tests
  - `JsonStreamParser` unit tests
  - `QueryPipeline` unit tests covering:
    - success lifecycle
    - failure path
    - retrieval staging
    - rerank staging
    - generation events
    - full `done` payload contract
    - final answer persistence
  - worker unit tests covering:
    - `run_query_pipeline(ctx, query_id)` delegation
    - worker startup dependency construction
    - worker shutdown cleanup
    - `WorkerSettings` hook exposure
- Still missing:
  - end-to-end ARQ integration tests
  - SSE event-order tests driven by real running worker + pipeline
  - live-worker smoke coverage for the refactored Qdrant sparse-query contract

### Manual Verification

1. `docker compose up --build` — verify all services start (backend, worker, frontend, postgres, qdrant, redis).
2. Open `http://localhost:3000`, type a query, verify: route badge appears → retrieval progress → sentences stream in → citations are clickable → evidence panel shows source details.
3. Hit `/health` endpoint — verify Qdrant collection now shows the named vector configuration.
